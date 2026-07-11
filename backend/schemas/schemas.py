"""
schemas/schemas.py – Pydantic request & response models
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ───────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str
    phone:    str
    email:    Optional[str] = None
    password: str
    role:     str = "customer"

class LoginRequest(BaseModel):
    phone:    str
    password: str


# ── User ───────────────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id:   int
    name: str
    phone: str
    role: str
    class Config:
        from_attributes = True


# ── MenuItem ───────────────────────────────────────────────────────────────────
class MenuItemCreate(BaseModel):
    name:          str
    description:   Optional[str]  = None
    price:         float
    cuisine_tags:  str             = ""
    image_url:     Optional[str]  = None   # set after upload-image call
    is_flash_deal: bool            = False
    flash_price:   Optional[float] = None

class MenuItemOut(BaseModel):
    id:            int
    cook_id:       int
    name:          str
    description:   Optional[str]  = None
    price:         float
    cuisine_tags:  str
    image_url:     Optional[str]  = None
    is_flash_deal: bool
    flash_price:   Optional[float] = None
    available:     bool
    class Config:
        from_attributes = True


# ── Order ──────────────────────────────────────────────────────────────────────
class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity:     int = 1

class OrderCreate(BaseModel):
    items:            List[OrderItemIn]
    payment_method:   str            = "cash"
    delivery_address: Optional[str]  = None
    delivery_lat:     Optional[float] = None
    delivery_lng:     Optional[float] = None
    notes:            Optional[str]   = None

class OrderOut(BaseModel):
    id:               int
    customer_id:      int
    status:           str
    total:            float
    payment_method:   str
    delivery_address: Optional[str] = None
    created_at:       datetime
    class Config:
        from_attributes = True


# ── Recommend ─────────────────────────────────────────────────────────────────
class RecommendRequest(BaseModel):
    user_id: int
    budget:  Optional[float] = None
    lat:     Optional[float] = None
    lng:     Optional[float] = None

class RecommendOut(BaseModel):
    menu_item_id: int
    name:         str
    price:        float
    cook_kasi:    str
    score:        float
