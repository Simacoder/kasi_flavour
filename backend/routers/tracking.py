"""
routers/tracking.py – Real-time GPS tracking via WebSocket
============================================================
Flow:
  1. Driver connects:  ws://host/api/track/driver/{driver_id}
     – sends JSON: {"order_id": 5, "lat": -26.2, "lng": 28.04}

  2. Customer connects: ws://host/api/track/order/{order_id}
     – receives live driver location updates

Connection manager keeps an in-memory dict so any driver message
is fanned out to all customers watching that order.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import json
from typing import Dict, List

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        # order_id → list of customer WebSocket connections
        self.order_listeners: Dict[int, List[WebSocket]] = {}
        # driver_id → WebSocket
        self.driver_connections: Dict[int, WebSocket] = {}

    async def connect_driver(self, driver_id: int, ws: WebSocket):
        await ws.accept()
        self.driver_connections[driver_id] = ws

    async def connect_customer(self, order_id: int, ws: WebSocket):
        await ws.accept()
        self.order_listeners.setdefault(order_id, []).append(ws)

    def disconnect_driver(self, driver_id: int):
        self.driver_connections.pop(driver_id, None)

    def disconnect_customer(self, order_id: int, ws: WebSocket):
        listeners = self.order_listeners.get(order_id, [])
        if ws in listeners:
            listeners.remove(ws)

    async def broadcast_location(self, order_id: int, payload: dict):
        """Send driver location to all customers watching this order."""
        for ws in self.order_listeners.get(order_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                pass  # stale connection – cleaned up on disconnect


manager = ConnectionManager()


@router.websocket("/driver/{driver_id}")
async def driver_ws(driver_id: int, websocket: WebSocket):
    """Driver streams their GPS location."""
    await manager.connect_driver(driver_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            # payload: {"order_id": int, "lat": float, "lng": float}
            order_id = payload.get("order_id")
            if order_id:
                payload["driver_id"] = driver_id
                await manager.broadcast_location(order_id, payload)
    except WebSocketDisconnect:
        manager.disconnect_driver(driver_id)


@router.websocket("/order/{order_id}")
async def customer_ws(order_id: int, websocket: WebSocket):
    """Customer listens for driver location updates on their order."""
    await manager.connect_customer(order_id, websocket)
    try:
        while True:
            # keep connection alive; customer only receives, not sends
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_customer(order_id, websocket)


@router.get("/{order_id}")
def get_tracking_info(order_id: int):
    """HTTP fallback – returns whether a driver is currently connected."""
    connected_drivers = list(manager.driver_connections.keys())
    return {
        "order_id": order_id,
        "live_tracking_available": len(manager.order_listeners.get(order_id, [])) > 0,
        "active_drivers": len(connected_drivers),
    }
