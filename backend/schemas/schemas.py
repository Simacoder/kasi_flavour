"""
schemas/schemas.py – Pydantic request & response models
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from models.models import UserRole, OrderStatus, PaymentMethod


# ── Auth ───────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str
    phone:    str
    email:    Optional[EmailStr] = None
    password: str
    role:     UserRole = UserRole.customer

class LoginRequest(BaseModel):
    phone:    str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


# ── User ───────────────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id:    int
    name:  str
    phone: str
    role:  UserRole
    class Config:
        from_attributes = True


# ── Cook ───────────────────────────────────────────────────────────────────────
class CookOut(BaseModel):
    id:       int
    kasi:     str
    bio:      Optional[str]
    rating:   float
    badges:   str
    class Config:
        from_attributes = True


# ── MenuItem ───────────────────────────────────────────────────────────────────
class MenuItemCreate(BaseModel):
    name:          str
    description:   Optional[str] = None
    price:         float
    cuisine_tags:  str = ""
    image_url:     Optional[str] = None
    is_flash_deal: bool = False
    flash_price:   Optional[float] = None

class MenuItemOut(MenuItemCreate):
    id:        int
    cook_id:   int
    available: bool
    class Config:
        from_attributes = True


# ── Order ──────────────────────────────────────────────────────────────────────
class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity:     int = 1

class OrderCreate(BaseModel):
    items:            List[OrderItemIn]
    payment_method:   PaymentMethod = PaymentMethod.cash
    delivery_address: Optional[str] = None
    delivery_lat:     Optional[float] = None
    delivery_lng:     Optional[float] = None
    notes:            Optional[str] = None

class OrderOut(BaseModel):
    id:         int
    status:     OrderStatus
    total:      float
    created_at: datetime
    class Config:
        from_attributes = True


# ── Tracking ───────────────────────────────────────────────────────────────────
class LocationUpdate(BaseModel):
    driver_id:  int
    order_id:   int
    lat:        float
    lng:        float


# ── Recommend ─────────────────────────────────────────────────────────────────
class RecommendRequest(BaseModel):
    user_id:  int
    budget:   Optional[float] = None
    lat:      Optional[float] = None
    lng:      Optional[float] = None

class RecommendOut(BaseModel):
    menu_item_id: int
    name:         str
    price:        float
    cook_kasi:    str
    score:        float
