"""
routers/orders.py – Place, view and update orders
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.models import Order, OrderItem, MenuItem, OrderStatus
from schemas.schemas import OrderCreate, OrderOut

router = APIRouter()


@router.post("/", response_model=OrderOut, status_code=201)
def place_order(body: OrderCreate, db: Session = Depends(get_db)):
    """Customer places a new order."""
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
        customer_id      = 1,          # replace with JWT user id
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
def list_orders(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.query(Order).offset(skip).limit(limit).all()
