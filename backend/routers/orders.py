"""
routers/orders.py – Place, view and update orders
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from jose import jwt, JWTError
import os

from database import get_db
from models.models import Order, OrderItem, MenuItem, OrderStatus
from schemas.schemas import OrderCreate, OrderOut

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "kasi-flavour-secret-change-in-prod")
ALGORITHM  = "HS256"


# ── JWT helper ────────────────────────────────────────────────────────────────
# FIX: order placement was using a hardcoded customer_id = 1 for every single
# order ("replace with JWT user id" — a leftover placeholder that was never
# finished). This either crashed with a foreign-key/integrity error (if no
# user with id=1 exists in the database) or silently attributed every order
# to the wrong customer. Same JWT decoding pattern already used successfully
# in routers/menus.py.
def _get_user_id(authorization: str = "") -> Optional[int]:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub", 0)) or None
    except JWTError:
        return None


@router.post("/", response_model=OrderOut, status_code=201)
def place_order(
    body:          OrderCreate,
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    """Customer places a new order."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    total = 0.0
    items_to_add = []
    for item_in in body.items:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item_in.menu_item_id,
            MenuItem.available == True
        ).first()
        if not menu_item:
            raise HTTPException(
                status_code=404,
                detail=f"Menu item {item_in.menu_item_id} not found or unavailable"
            )
        price = menu_item.flash_price if menu_item.is_flash_deal and menu_item.flash_price else menu_item.price
        total += price * item_in.quantity
        items_to_add.append((menu_item, item_in.quantity, price))

    # Add delivery fee (R8 default)
    total += 8.0

    order = Order(
        customer_id      = user_id,   # FIX: was hardcoded to 1
        total            = round(total, 2),
        payment_method   = body.payment_method,
        delivery_address = body.delivery_address,
        delivery_lat     = body.delivery_lat,
        delivery_lng     = body.delivery_lng,
        notes            = body.notes,
    )
    db.add(order)
    db.flush()  # get order.id before committing

    for menu_item, qty, price in items_to_add:
        db.add(OrderItem(
            order_id     = order.id,
            menu_item_id = menu_item.id,
            quantity     = qty,
            unit_price   = price,
        ))

    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status")
def update_order_status(order_id: int, status: OrderStatus, db: Session = Depends(get_db)):
    """Cook or driver updates the order status."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status
    db.commit()
    return {"id": order.id, "status": order.status}


@router.get("/", response_model=List[OrderOut])
def list_orders(
    authorization: str     = Header(default=""),
    skip:          int     = 0,
    limit:         int     = 20,
    db:            Session = Depends(get_db),
):
    """
    FIX: was returning ALL orders from ALL customers to anyone who called
    this — a real privacy bug. Now scoped to the logged-in user's own orders.
    """
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return (
        db.query(Order)
        .filter(Order.customer_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )