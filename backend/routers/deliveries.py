"""
routers/deliveries.py – Driver order acceptance and delivery status
======================================================================
NEW FILE. Your data model already had Driver and Delivery tables ready
(driver_id, driver_lat/lng, eta, status, fee) but nothing used them yet —
there was no way for a driver to see or accept an order. This wires that up.

Flow:
  1. Driver logs in, GET /api/deliveries/me auto-creates their Driver
     record if it doesn't exist yet (same pattern as Cook auto-creation
     in routers/menus.py).
  2. GET /api/deliveries/available — orders that are "ready" for pickup
     and don't have a driver assigned yet.
  3. POST /api/deliveries/{order_id}/accept — driver claims the order.
     Creates/updates the Delivery row and advances Order.status.
  4. PATCH /api/deliveries/{order_id}/status — driver marks delivered.
  5. GPS location itself still streams over the existing WebSocket in
     tracking.py (ws://.../api/track/driver/{driver_id}) — this router
     only handles the "who's delivering this order" part.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from jose import jwt, JWTError
import os

from database import get_db
from models.models import Order, Delivery, Driver, User, OrderStatus

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "kasi-flavour-secret-change-in-prod")
ALGORITHM  = "HS256"


def _get_user_id(authorization: str = "") -> Optional[int]:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub", 0)) or None
    except JWTError:
        return None


def _resolve_driver(user_id: int, db: Session) -> Driver:
    """Get or auto-create a Driver record for this user — same pattern
    as _resolve_cook in routers/menus.py."""
    driver = db.query(Driver).filter(Driver.user_id == user_id).first()
    if not driver:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        driver = Driver(user_id=user_id, vehicle="bicycle", available=True, rating=0.0)
        db.add(driver)
        db.commit()
        db.refresh(driver)
    return driver


def _require_driver(authorization: str, db: Session) -> Driver:
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _resolve_driver(user_id, db)


# ── 1. Get/create my driver profile  GET /api/deliveries/me ───────────────────
@router.get("/me")
def get_my_driver_profile(
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    driver = _require_driver(authorization, db)
    return {
        "id":        driver.id,
        "vehicle":   driver.vehicle,
        "available": driver.available,
        "rating":    driver.rating,
    }


# ── 2. List orders available for pickup  GET /api/deliveries/available ────────
@router.get("/available")
def list_available_orders(
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    _require_driver(authorization, db)  # any logged-in driver can view

    # Orders marked "ready" by the cook that don't have a driver assigned yet.
    orders = (
        db.query(Order)
        .outerjoin(Delivery, Delivery.order_id == Order.id)
        .filter(
            Order.status == OrderStatus.ready,
            (Delivery.id.is_(None)) | (Delivery.driver_id.is_(None)),
        )
        .all()
    )
    return [
        {
            "id":               o.id,
            "delivery_address": o.delivery_address,
            "delivery_lat":     o.delivery_lat,
            "delivery_lng":     o.delivery_lng,
            "total":            o.total,
            "notes":            o.notes,
            "created_at":       o.created_at,
        }
        for o in orders
    ]


# ── 3. Accept an order  POST /api/deliveries/{order_id}/accept ────────────────
@router.post("/{order_id}/accept")
def accept_order(
    order_id:      int,
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    driver = _require_driver(authorization, db)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.ready:
        raise HTTPException(
            status_code=400,
            detail=f"Order is not ready for pickup (status: {order.status.value})",
        )

    delivery = db.query(Delivery).filter(Delivery.order_id == order_id).first()
    if delivery and delivery.driver_id:
        raise HTTPException(status_code=409, detail="Order already claimed by another driver")

    if not delivery:
        delivery = Delivery(order_id=order_id, driver_id=driver.id, status="picked_up")
        db.add(delivery)
    else:
        delivery.driver_id = driver.id
        delivery.status    = "picked_up"

    order.status = OrderStatus.picked_up
    db.commit()
    db.refresh(delivery)

    return {
        "order_id":  order_id,
        "driver_id": driver.id,
        "status":    delivery.status,
    }


# ── 4. Update delivery status  PATCH /api/deliveries/{order_id}/status ────────
@router.patch("/{order_id}/status")
def update_delivery_status(
    order_id:      int,
    status:        str,   # "picked_up" | "delivered"
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    driver = _require_driver(authorization, db)

    delivery = db.query(Delivery).filter(Delivery.order_id == order_id).first()
    if not delivery or delivery.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Delivery not found for this driver")

    order = db.query(Order).filter(Order.id == order_id).first()

    delivery.status = status
    if status == "delivered":
        order.status = OrderStatus.delivered

    db.commit()
    return {"order_id": order_id, "status": delivery.status}


# ── 5. My active deliveries  GET /api/deliveries/my ────────────────────────────
@router.get("/my")
def list_my_deliveries(
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    driver = _require_driver(authorization, db)
    deliveries = db.query(Delivery).filter(
        Delivery.driver_id == driver.id,
        Delivery.status != "delivered",
    ).all()
    return [
        {
            "order_id": d.order_id,
            "status":   d.status,
            "fee":      d.fee,
        }
        for d in deliveries
    ]