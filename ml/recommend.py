"""
ml/recommend.py – Kasi Flavour Hybrid Recommendation Engine
============================================================
Architecture: 3-signal weighted ensemble

  Signal 1 — Collaborative Filtering  (40%)
    SVD matrix factorisation on user-item order history.
    "Users who ordered what you ordered also liked..."
    Falls back to 0.5 when no model trained yet.

  Signal 2 — Content-Based Filtering  (35%)
    Jaccard similarity between the user's cuisine tag history
    and each menu item's tags.
    "You liked pap,traditional — here's more like that."

  Signal 3 — Contextual Filtering     (25%)
    • Time-of-day meal boost (breakfast/lunch/dinner windows)
    • Haversine distance penalty (closer cook = higher score)
    • Budget hard filter (skip items above budget)
    • Cook rating boost (highly-rated cooks score higher)

Result: top-N items ranked by final_score ∈ [0, 1]
"""

import sys, os, math, pickle, logging
from datetime import datetime
from typing import Optional, List

import numpy as np

# ── Path: make backend/ importable when called from ml/ ──────────────────────
_ml_dir      = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_ml_dir, ".."))
_backend_dir  = os.path.join(_project_root, "backend")
for _p in [_backend_dir, _project_root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger     = logging.getLogger(__name__)
MODEL_PATH = os.path.join(_ml_dir, "model.pkl")

# ── Load trained model at import time ────────────────────────────────────────
_model = None

def reload_model():
    """Call after training to hot-swap the model without restarting."""
    global _model
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        logger.info("Recommendation model loaded from %s", MODEL_PATH)
    else:
        logger.warning("No model.pkl found — collaborative signal will return 0.5")

reload_model()


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL 1 — COLLABORATIVE FILTERING
# ══════════════════════════════════════════════════════════════════════════════

def _collaborative_score(user_id: int, menu_item_id: int) -> float:
    """
    Predict user-item affinity using the trained SVD model.
    Returns a score in [0, 1]. Falls back to 0.5 (neutral) when:
      - model not trained yet
      - user/item not seen during training (cold start)
    """
    if _model is None:
        return 0.5
    try:
        raw = _model.predict([[user_id, menu_item_id]])[0]
        return float(np.clip(raw, 0.0, 1.0))
    except Exception:
        return 0.5


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL 2 — CONTENT-BASED FILTERING
# ══════════════════════════════════════════════════════════════════════════════

def _content_score(user_tags: List[str], item_tags: str) -> float:
    """
    Jaccard similarity: |user_tags ∩ item_tags| / |user_tags ∪ item_tags|

    Returns 0.5 (neutral) when no history exists (cold start).
    Returns 1.0 when all item tags match the user's history.
    Returns 0.0 when no tags overlap at all.
    """
    if not user_tags or not item_tags:
        return 0.5

    item_set = {t.strip().lower() for t in item_tags.split(",") if t.strip()}
    user_set = {t.strip().lower() for t in user_tags if t.strip()}

    if not item_set or not user_set:
        return 0.5

    intersection = len(item_set & user_set)
    union        = len(item_set | user_set)
    return intersection / union if union else 0.5


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL 3 — CONTEXTUAL FILTERING
# ══════════════════════════════════════════════════════════════════════════════

def _time_weight(hour_sast: int) -> float:
    """
    Boost meals by time-of-day relevance (SAST).
    Breakfast 06-09: 1.3x  |  Lunch 11-14: 1.4x  |  Dinner 17-21: 1.5x
    Late night 22-05: 0.8x (suppress — fewer deliveries)
    """
    if  6 <= hour_sast <  9: return 1.30   # breakfast window
    if 11 <= hour_sast < 14: return 1.40   # lunch peak
    if 14 <= hour_sast < 17: return 1.10   # afternoon
    if 17 <= hour_sast < 21: return 1.50   # dinner peak (highest)
    if 21 <= hour_sast < 23: return 0.90   # late evening
    return 0.80                             # late night / early morning


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine great-circle distance in kilometres."""
    R    = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(max(0, a)))


def _distance_penalty(user_lat: float, user_lng: float,
                       cook_lat: Optional[float], cook_lng: Optional[float],
                       max_radius_km: float = 20.0) -> float:
    """
    Linear distance penalty: 1.0 at 0 km → 0.2 at max_radius_km.
    Returns 1.0 (no penalty) when cook location is unknown.
    """
    if cook_lat is None or cook_lng is None:
        return 1.0
    km = _haversine_km(user_lat, user_lng, cook_lat, cook_lng)
    return max(0.2, 1.0 - (km / max_radius_km))


def _cook_rating_boost(rating: float) -> float:
    """
    Smooth cook rating boost: 4.5+ → ×1.15, 3.0 → ×1.0, <2.0 → slight penalty.
    Maps [0, 5] → [0.85, 1.15] via linear interpolation.
    """
    return 0.85 + (rating / 5.0) * 0.30


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def get_recommendations(
    user_id: int,
    db,
    budget:       Optional[float] = None,
    lat:          Optional[float] = None,
    lng:          Optional[float] = None,
    top_n:        int             = 5,
    max_radius_km: float          = 20.0,
) -> List[dict]:
    """
    Return top-N meal recommendations for a user.

    Parameters
    ----------
    user_id  : authenticated customer ID
    db       : SQLAlchemy session
    budget   : optional max price filter (R)
    lat/lng  : optional user GPS for distance scoring
    top_n    : number of results to return (default 5)

    Returns
    -------
    List of dicts: [{ menu_item_id, name, price, cook_kasi, score }, ...]
    Sorted descending by score ∈ [0, 1].
    """
    from models.models import MenuItem, Cook, Order, OrderItem, User

    # ── SAST hour for contextual scoring ─────────────────────────────────────
    hour_sast = (datetime.utcnow().hour + 2) % 24

    # ── Build user taste profile from order history ───────────────────────────
    past = (
        db.query(MenuItem.cuisine_tags)
        .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.customer_id == user_id)
        .all()
    )
    user_tags: List[str] = []
    for (tags,) in past:
        user_tags.extend(t.strip() for t in (tags or "").split(",") if t.strip())

    # ── Fetch all available menu items with cook + cook's user (for GPS) ─────
    rows = (
        db.query(MenuItem, Cook)
        .join(Cook, Cook.id == MenuItem.cook_id)
        .filter(MenuItem.available == True)
        .all()
    )

    # Lazy-load cook user GPS in one query to avoid N+1
    cook_ids  = list({cook.user_id for _, cook in rows})
    cook_users = {u.id: u for u in db.query(User).filter(User.id.in_(cook_ids)).all()}

    scored = []
    for menu_item, cook in rows:

        # Effective price (flash deal if active)
        price = (
            menu_item.flash_price
            if menu_item.is_flash_deal and menu_item.flash_price
            else menu_item.price
        )

        # Hard budget filter
        if budget is not None and price > budget:
            continue

        # ── Signal 1: Collaborative ───────────────────────────────────────
        s_collab = _collaborative_score(user_id, menu_item.id)

        # ── Signal 2: Content-based ───────────────────────────────────────
        s_content = _content_score(user_tags, menu_item.cuisine_tags or "")

        # ── Signal 3: Contextual ──────────────────────────────────────────
        time_w    = _time_weight(hour_sast)
        rating_b  = _cook_rating_boost(cook.rating or 0.0)

        cook_u    = cook_users.get(cook.user_id)
        cook_lat  = cook_u.lat if cook_u else None
        cook_lng  = cook_u.lng if cook_u else None

        dist_pen  = (
            _distance_penalty(lat, lng, cook_lat, cook_lng, max_radius_km)
            if lat is not None and lng is not None
            else 1.0
        )

        s_context = time_w * dist_pen * rating_b

        # ── Weighted combination ──────────────────────────────────────────
        final_score = round(
            0.40 * s_collab +
            0.35 * s_content +
            0.25 * min(s_context, 1.0),   # cap contextual at 1.0
            4
        )

        scored.append({
            "menu_item_id":  menu_item.id,
            "name":          menu_item.name,
            "price":         round(price, 2),
            "cook_kasi":     cook.kasi or "",
            "score":         final_score,
            # Extra fields for frontend display
            "image_url":     menu_item.image_url,
            "cuisine_tags":  menu_item.cuisine_tags or "",
            "description":   menu_item.description or "",
            "_debug": {
                "collab":   round(s_collab, 4),
                "content":  round(s_content, 4),
                "context":  round(s_context, 4),
                "time_w":   round(time_w, 2),
                "dist_pen": round(dist_pen, 2),
                "rating_b": round(rating_b, 2),
            }
        })

    # Sort descending by final score
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]