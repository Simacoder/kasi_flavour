# Kasi Flavour — ML Recommendation System

## Architecture Overview

```
Order history (MySQL)
        │
        ▼
ml/train.py  ──────────────────────────────────────────────────────────
  │  1. Fetch real interactions (user_id × item_id × quantity)        │
  │  2. Log-normalise quantity → implicit rating [0,1]                │
  │  3. Try scikit-surprise SVD  (best, needs Cython build)           │
  │     vs NMF  (5-fold CV — picks winner on RMSE)                   │
  │  4. Fallback: sklearn SGDRegressor (always works, no extra deps)  │
  │  5. Evaluate Precision@5 + Recall@5 on held-out 20%              │
  │  6. Save model.pkl + training_report.json                         │
  └──────────────────────────────────────────────────────────────────-─

model.pkl
        │
        ▼
ml/recommend.py ─── 3-Signal Weighted Ensemble ─────────────────────────
  │
  ├── Signal 1: Collaborative (40%)  ← model.pkl SVD prediction
  ├── Signal 2: Content-based (35%)  ← Jaccard(user_tags, item_tags)
  └── Signal 3: Contextual   (25%)   ← time_weight × dist_penalty × cook_rating
        │
        ▼
  final_score = 0.40×collab + 0.35×content + 0.25×context
        │
        ▼
  Top-5 ranked meals → POST /api/recommend/ → frontend
```

## Quick Start

```bash
# 1. Install ML dependencies
pip install -r ml/requirements_ml.txt

# 2. Train the model (uses real orders if they exist, else synthetic)
cd backend
python ../ml/train.py

# Output:
# ════════════════════════════════════════════════════
#   KASI FLAVOUR — ML TRAINING PIPELINE
#   Started: 2025-06-15T10:32:01
# ════════════════════════════════════════════════════
# Querying order history from database…
#   Real interactions loaded: 247 (from 34 users, 18 items)
# Training SVD collaborative filter (scikit-surprise)…
#   SVD  RMSE=0.1423  MAE=0.0987
#   NMF  RMSE=0.1612  MAE=0.1134
#   Best surprise model: SVD
# Model saved → ml/model.pkl
# Report saved → ml/training_report.json
# ════════════════════════════════════════════════════
#   TRAINING COMPLETE
# ════════════════════════════════════════════════════
#
# ✅ Training complete. Summary:
#    Model:        SVD
#    Interactions: 247
#    Users:        34
#    Items:        18
#    Precision@5:  0.3200
#    Recall@5:     0.1800

# 3. Force synthetic data (day-1 before real orders)
python ../ml/train.py --synthetic

# 4. Check metrics without retraining
python ../ml/train.py --eval-only
```

## Signal Details

### Signal 1 — Collaborative Filtering (40%)
- Algorithm: SVD matrix factorisation (scikit-surprise)
- Fallback:  SGDRegressor (sklearn, always available)
- Training:  5-fold CV comparing SVD vs NMF on RMSE
- Cold start: returns 0.5 (neutral) for unseen user/item pairs

### Signal 2 — Content-Based Filtering (35%)
- Method: Jaccard similarity on cuisine tags
- User profile: aggregated from all past orders
- Formula: |user_tags ∩ item_tags| / |user_tags ∪ item_tags|
- Cold start: returns 0.5 (neutral) when no order history

### Signal 3 — Contextual Filtering (25%)
Combines 3 sub-signals:

| Sub-signal | Formula | Range |
|---|---|---|
| Time-of-day | Boost by meal-window (breakfast/lunch/dinner) | 0.8–1.5× |
| Distance | Haversine km → linear penalty (max 20 km) | 0.2–1.0 |
| Cook rating | Linear map [0,5] → [0.85, 1.15] | 0.85–1.15 |

### Final Score
```
final_score = 0.40 × collab + 0.35 × content + 0.25 × min(context, 1.0)
```
All scores are in [0, 1]. Result is sorted descending, top-5 returned.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/recommend/` | Get top-5 recommendations |
| POST | `/api/recommend/debug` | Full signal breakdown (dev) |
| GET  | `/api/recommend/report` | Latest training metrics |
| POST | `/api/recommend/retrain` | Trigger background retrain |

### Example request
```json
POST /api/recommend/
{
  "user_id": 5,
  "budget":  80.0,
  "lat":     -26.2485,
  "lng":     27.8546
}
```

### Example response
```json
[
  { "menu_item_id": 3, "name": "Pap & Wors",   "price": 45.00, "cook_kasi": "Soweto",   "score": 0.7823 },
  { "menu_item_id": 7, "name": "Umngqusho",     "price": 38.00, "cook_kasi": "Alexandra","score": 0.7201 },
  { "menu_item_id": 1, "name": "Braai Chicken", "price": 60.00, "cook_kasi": "Tembisa",  "score": 0.6915 }
]
```

### Debug endpoint (includes signal breakdown)
```json
POST /api/recommend/debug
→
[
  {
    "menu_item_id": 3,
    "score": 0.7823,
    "_debug": {
      "collab":   0.82,
      "content":  0.75,
      "context":  0.79,
      "time_w":   1.40,
      "dist_pen": 0.91,
      "rating_b": 1.12
    }
  }
]
```

## Auto-Retrain

Add this to `backend/main.py` to enable automatic daily retraining:

```python
from ml.retrain_scheduler import lifespan
app = FastAPI(lifespan=lifespan, title="Kasi Flavour API")
```

The scheduler:
- Checks on startup if model is missing or > 24h old
- Retrains in background (non-blocking)
- Retrains every 24h automatically
- Calls `reload_model()` to hot-swap without restart

## Training Report (`ml/training_report.json`)

```json
{
  "trained_at":      "2025-06-15T10:32:05",
  "model":           "SVD",
  "interactions":    247,
  "unique_users":    34,
  "unique_items":    18,
  "sparsity_pct":    59.7,
  "cv_results": {
    "SVD": { "rmse": 0.1423, "mae": 0.0987 },
    "NMF": { "rmse": 0.1612, "mae": 0.1134 }
  },
  "top_n_metrics": {
    "precision@5": 0.32,
    "recall@5":    0.18
  },
  "data_source": "real_orders"
}
```