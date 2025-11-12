import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId
import stripe

from database import db, create_document, get_documents
from schemas import Product, Category, Order, OrderItem

app = FastAPI(title="WoodenMart API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
if STRIPE_SECRET:
    stripe.api_key = STRIPE_SECRET

# --- Auth ---
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "woodenmart@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "woodenmart@1")

class AuthRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    role: str
    email: EmailStr

# NOTE: Simple demo auth (no JWT). Returns a static token if credentials match.
@app.post("/auth/login", response_model=AuthResponse)
def login(req: AuthRequest):
    if req.email.lower() == ADMIN_EMAIL.lower() and req.password == ADMIN_PASSWORD:
        return AuthResponse(token="admin-token", role="admin", email=req.email)
    # Could extend with seller/user auth later
    raise HTTPException(status_code=401, detail="Invalid credentials")


class ProductCreate(Product):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    images: Optional[List[str]] = None
    category: Optional[str] = None
    stock: Optional[int] = None
    featured: Optional[bool] = None

class CheckoutRequest(BaseModel):
    items: List[dict]
    customer_email: str

@app.get("/")
def root():
    return {"name": "WoodenMart API", "status": "ok"}

@app.get("/products")
def list_products():
    products = get_documents("product")
    for p in products:
        p["id"] = str(p.pop("_id"))
    return products

@app.post("/products")
def create_product(payload: ProductCreate):
    product_id = create_document("product", payload)
    return {"id": product_id}

@app.patch("/products/{product_id}")
def update_product(product_id: str, payload: ProductUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    res = db["product"].update_one({"_id": ObjectId(product_id)}, {"$set": data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"updated": True}

@app.delete("/products/{product_id}")
def delete_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    res = db["product"].delete_one({"_id": ObjectId(product_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"deleted": True}

@app.get("/orders")
def list_orders():
    orders = get_documents("order")
    for o in orders:
        o["id"] = str(o.pop("_id"))
    return orders

@app.post("/checkout")
def checkout(req: CheckoutRequest):
    if not STRIPE_SECRET:
        # Simulate success for demo if no Stripe configured
        # Create order in DB with status paid
        items: List[OrderItem] = []
        total = 0
        for it in req.items:
            prod = db["product"].find_one({"_id": ObjectId(it["product_id"])})
            if not prod:
                raise HTTPException(status_code=404, detail="Product not found")
            qty = int(it.get("quantity", 1))
            unit_price = float(prod.get("price", 0))
            subtotal = unit_price * qty
            items.append(OrderItem(
                product_id=str(prod["_id"]),
                title=prod.get("title", ""),
                unit_price=unit_price,
                quantity=qty,
                subtotal=subtotal
            ))
            total += subtotal
        order = Order(user_email=req.customer_email, items=items, total=total)
        order_id = create_document("order", order)
        return {"success": True, "order_id": order_id, "payment_simulated": True}

    # Real Stripe flow
    try:
        line_items = []
        for it in req.items:
            prod = db["product"].find_one({"_id": ObjectId(it["product_id"])})
            if not prod:
                raise HTTPException(status_code=404, detail="Product not found")
            qty = int(it.get("quantity", 1))
            line_items.append({
                "price_data": {
                    "currency": prod.get("currency", "inr"),
                    "product_data": {"name": prod.get("title", "Item")},
                    # Stripe expects amount in smallest unit (paise)
                    "unit_amount": int(float(prod.get("price", 0)) * 100)
                },
                "quantity": qty
            })
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/checkout/success",
            cancel_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/checkout/cancel",
            customer_email=req.customer_email
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/test")
def test_database():
    resp = {"backend": "running", "database": "not configured"}
    try:
        if db:
            resp["database"] = "connected"
            resp["collections"] = db.list_collection_names()
    except Exception as e:
        resp["error"] = str(e)
    return resp

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
