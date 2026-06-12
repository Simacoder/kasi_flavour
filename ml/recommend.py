"""
ml/recommend.py – Kasi Flavour ML Recommendation Engine
=========================================================
Three signals combined:
  1. Collaborative filtering  – "users like you ordered..."
  2. Content-based filtering  – taste tags + cuisine type match
  3. Contextual filtering     – time of day, distance, budget
"""

import sys, os

# ── Add backend/ to path so models/ is importable from ml/ ───────────────────
_ml_dir      = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_ml_dir, "..", "backend"))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import math
import pickle
from datetime import datetime
from typing import Optional, List

import numpy as np

MODEL_PATH = os.path.join(_ml_dir, "model.pkl")

# ── Load model at import time (silently skip if not trained yet) ──────────────
_model = None

def _load_model():
    global _model
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)

_load_model()


# ── Haversine distance (km) ───────────────────────────────────────────────────
def _distance_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Time-of-day weight ────────────────────────────────────────────────────────
def _time_weight(hour: int) -> float:
    if 6  <= hour < 9:  return 1.3   # breakfast
    if 11 <= hour < 14: return 1.4   # lunch peak
    if 17 <= hour < 21: return 1.5   # dinner peak
    return 1.0


# ── Collaborative score ───────────────────────────────────────────────────────
def _collaborative_score(user_id: int, menu_item_id: int) -> float:
    if _model is None:
        return 0.5
    try:
        score = _model.predict([[user_id, menu_item_id]])[0]
        return float(np.clip(score, 0, 1))
    except Exception:
        return 0.5


# ── Content-based score ───────────────────────────────────────────────────────
def _content_score(user_tags: List[str], item_tags: str) -> float:
    if not user_tags or not item_tags:
        return 0.5
    item_set = {t.strip().lower() for t in item_tags.split(",") if t.strip()}
    user_set = {t.strip().lower() for t in user_tags}
    if not item_set or not user_set:
        return 0.5
    intersection = len(item_set & user_set)
    union = len(item_set | user_set)
    return intersection / union if union else 0.5


# ── Main recommendation function ──────────────────────────────────────────────
def get_recommendations(
    user_id: int,
    db,
    budget:  Optional[float] = None,
    lat:     Optional[float] = None,
    lng:     Optional[float] = None,
    top_n:   int = 5,
) -> List[dict]:

    # Import models here to avoid circular import at module load time
    from models.models import MenuItem, Cook, Order, OrderItem

    hour = (datetime.utcnow().hour + 2) % 24  # SAST = UTC+2

    # ── User's past cuisine tags ──────────────────────────────────────────────
    past_items = (
        db.query(MenuItem.cuisine_tags)
        .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Order,     Order.id == OrderItem.order_id)
        .filter(Order.customer_id == user_id)
        .all()
    )
    user_tags: List[str] = []
    for (tags,) in past_items:
        user_tags.extend(t.strip() for t in (tags or "").split(",") if t.strip())

    # ── All available menu items ──────────────────────────────────────────────
    items = (
        db.query(MenuItem, Cook)
        .join(Cook, Cook.id == MenuItem.cook_id)
        .filter(MenuItem.available == True)
        .all()
    )

    scored = []
    for menu_item, cook in items:
        price = (
            menu_item.flash_price
            if menu_item.is_flash_deal and menu_item.flash_price
            else menu_item.price
        )

        if budget and price > budget:
            continue

        collab  = _collaborative_score(user_id, menu_item.id)
        content = _content_score(user_tags, menu_item.cuisine_tags or "")

        time_boost       = _time_weight(hour)
        distance_penalty = 1.0

        if lat and lng:
            cook_user = cook.user if hasattr(cook, "user") else None
            if cook_user and cook_user.lat and cook_user.lng:
                km = _distance_km(lat, lng, cook_user.lat, cook_user.lng)
                distance_penalty = max(0.2, 1 - (km / 20))

        contextual  = time_boost * distance_penalty
        final_score = round(0.40 * collab + 0.35 * content + 0.25 * contextual, 4)

        scored.append({
            "menu_item_id": menu_item.id,
            "name":         menu_item.name,
            "price":        round(price, 2),
            "cook_kasi":    cook.kasi or "",
            "score":        final_score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]