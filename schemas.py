"""
WoodenMart Schemas

Define MongoDB collection schemas using Pydantic models.
Each class maps to a collection with lowercase name.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class Category(BaseModel):
    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="URL-friendly slug")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in base currency")
    currency: str = Field("inr", description="ISO currency code, default INR")
    images: List[str] = Field(default_factory=list, description="Image URLs")
    category: Optional[str] = Field(None, description="Category slug")
    stock: int = Field(0, ge=0, description="Units in stock")
    featured: bool = Field(False, description="Whether featured on homepage")

class CartItem(BaseModel):
    product_id: str = Field(...)
    quantity: int = Field(1, ge=1)

class OrderItem(BaseModel):
    product_id: str
    title: str
    unit_price: float
    quantity: int
    subtotal: float

class Order(BaseModel):
    user_email: EmailStr
    items: List[OrderItem]
    total: float
    currency: str = "inr"
    status: str = Field("pending", description="pending, paid, failed, cancelled, shipped")
    payment_intent_id: Optional[str] = None

class AdminUser(BaseModel):
    email: EmailStr
    password_hash: str
    role: str = Field("admin")
