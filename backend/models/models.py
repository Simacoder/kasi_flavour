"""
models/models.py – SQLAlchemy ORM table definitions
Tables: User, Cook, Driver, MenuItem, Order, OrderItem, Delivery, Review
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    ForeignKey, DateTime, Text, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    customer = "customer"
    cook     = "cook"
    driver   = "driver"
    admin    = "admin"

class OrderStatus(str, enum.Enum):
    pending    = "pending"
    confirmed  = "confirmed"
    preparing  = "preparing"
    ready      = "ready"
    picked_up  = "picked_up"
    delivered  = "delivered"
    cancelled  = "cancelled"

class PaymentMethod(str, enum.Enum):
    card        = "card"
    mobile_money = "mobile_money"
    cash        = "cash"


# ── User ───────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    phone      = Column(String(20), unique=True, nullable=False)
    email      = Column(String(120), unique=True, nullable=True)
    password   = Column(String(255), nullable=False)
    role       = Column(Enum(UserRole), default=UserRole.customer)
    lat        = Column(Float, nullable=True)   # last known location
    lng        = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cook    = relationship("Cook",   back_populates="user", uselist=False)
    driver  = relationship("Driver", back_populates="user", uselist=False)
    orders  = relationship("Order",  back_populates="customer")
    reviews = relationship("Review", back_populates="reviewer")


# ── Cook ───────────────────────────────────────────────────────────────────────
class Cook(Base):
    __tablename__ = "cooks"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), unique=True)
    kasi        = Column(String(100))           # neighbourhood / township
    bio         = Column(Text, nullable=True)
    rating      = Column(Float, default=0.0)
    badges      = Column(String(255), default="")  # e.g. "Spicy Queen,Portion King"
    is_active   = Column(Boolean, default=True)

    user        = relationship("User",     back_populates="cook")
    menu_items  = relationship("MenuItem", back_populates="cook")
    reviews     = relationship("Review",   back_populates="cook")


# ── Driver ─────────────────────────────────────────────────────────────────────
class Driver(Base):
    __tablename__ = "drivers"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), unique=True)
    vehicle     = Column(String(50))            # "motorbike" | "bicycle" | "car"
    available   = Column(Boolean, default=True)
    rating      = Column(Float, default=0.0)
    lat         = Column(Float, nullable=True)  # live location
    lng         = Column(Float, nullable=True)

    user        = relationship("User",     back_populates="driver")
    deliveries  = relationship("Delivery", back_populates="driver")


# ── MenuItem ───────────────────────────────────────────────────────────────────
class MenuItem(Base):
    __tablename__ = "menu_items"

    id            = Column(Integer, primary_key=True, index=True)
    cook_id       = Column(Integer, ForeignKey("cooks.id"))
    name          = Column(String(150), nullable=False)
    description   = Column(Text, nullable=True)
    price         = Column(Float, nullable=False)
    cuisine_tags  = Column(String(255), default="")  # "pap,traditional,spicy"
    image_url     = Column(String(500), nullable=True)
    available     = Column(Boolean, default=True)
    is_flash_deal = Column(Boolean, default=False)
    flash_price   = Column(Float, nullable=True)
    flash_expires = Column(DateTime(timezone=True), nullable=True)

    cook        = relationship("Cook",      back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")


# ── Order ──────────────────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"

    id             = Column(Integer, primary_key=True, index=True)
    customer_id    = Column(Integer, ForeignKey("users.id"))
    status         = Column(Enum(OrderStatus), default=OrderStatus.pending)
    total          = Column(Float, nullable=False)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.cash)
    delivery_lat   = Column(Float, nullable=True)
    delivery_lng   = Column(Float, nullable=True)
    delivery_address = Column(String(300), nullable=True)
    notes          = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    customer    = relationship("User",      back_populates="orders")
    items       = relationship("OrderItem", back_populates="order")
    delivery    = relationship("Delivery",  back_populates="order", uselist=False)


# ── OrderItem ──────────────────────────────────────────────────────────────────
class OrderItem(Base):
    __tablename__ = "order_items"

    id           = Column(Integer, primary_key=True, index=True)
    order_id     = Column(Integer, ForeignKey("orders.id"))
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"))
    quantity     = Column(Integer, default=1)
    unit_price   = Column(Float, nullable=False)

    order     = relationship("Order",    back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")


# ── Delivery ───────────────────────────────────────────────────────────────────
class Delivery(Base):
    __tablename__ = "deliveries"

    id         = Column(Integer, primary_key=True, index=True)
    order_id   = Column(Integer, ForeignKey("orders.id"), unique=True)
    driver_id  = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    driver_lat = Column(Float, nullable=True)   # updated via WebSocket
    driver_lng = Column(Float, nullable=True)
    eta        = Column(DateTime(timezone=True), nullable=True)
    status     = Column(String(50), default="pending")
    fee        = Column(Float, default=8.0)     # R4–R12 per delivery

    order  = relationship("Order",  back_populates="delivery")
    driver = relationship("Driver", back_populates="deliveries")


# ── Review ─────────────────────────────────────────────────────────────────────
class Review(Base):
    __tablename__ = "reviews"

    id          = Column(Integer, primary_key=True, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    cook_id     = Column(Integer, ForeignKey("cooks.id"))
    rating      = Column(Integer, nullable=False)   # 1–5
    tags        = Column(String(255), default="")   # "Spicy Queen,Portion King"
    comment     = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    reviewer = relationship("User", back_populates="reviews")
    cook     = relationship("Cook", back_populates="reviews")
