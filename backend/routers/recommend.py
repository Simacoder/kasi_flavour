"""
routers/recommend.py – ML Recommendation API endpoint
======================================================
POST /api/recommend/
  Input:  { user_id, budget?, lat?, lng? }
  Output: top-5 scored meal recommendations

GET  /api/recommend/retrain
  Triggers a background model retrain (admin use)

GET  /api/recommend/report
  Returns the latest training_report.json
"""

import os, sys, json, asyncio, logging
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from database import get_db
from schemas.schemas import RecommendRequest, RecommendOut

router = logging.getLogger(__name__)
router = APIRouter()
log    = logging.getLogger(__name__)

_ML_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml"))
REPORT_PATH = os.path.join(_ML_DIR, "training_report.json")


# ── Recommendations ───────────────────────────────────────────────────────────
@router.post("/", response_model=List[RecommendOut])
def recommend(body: RecommendRequest, db: Session = Depends(get_db)):
    """
    Return top-5 personalised meal recommendations.
    Works immediately even before model is trained (falls back to 0.5 collab score).
    """
    try:
        from ml.recommend import get_recommendations
        results = get_recommendations(
            user_id = body.user_id,
            budget  = body.budget,
            lat     = body.lat,
            lng     = body.lng,
            db      = db,
        )
        # Strip internal _debug field before returning
        for r in results:
            r.pop("_debug", None)
            r.pop("image_url", None)
            r.pop("cuisine_tags", None)
            r.pop("description", None)
        return results
    except Exception as e:
        log.error("Recommendation error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Debug endpoint: returns full scores including signal breakdown ─────────────
@router.post("/debug")
def recommend_debug(body: RecommendRequest, db: Session = Depends(get_db)):
    """Returns recommendations with full signal breakdown (collab/content/context)."""
    try:
        from ml.recommend import get_recommendations
        return get_recommendations(
            user_id=body.user_id, budget=body.budget,
            lat=body.lat, lng=body.lng, db=db, top_n=10,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Training report ───────────────────────────────────────────────────────────
@router.get("/report")
def training_report():
    """Return latest training metrics (RMSE, MAE, Precision@5, Recall@5)."""
    if not os.path.exists(REPORT_PATH):
        return {"status": "no_model_trained", "hint": "Run: python ml/train.py"}
    with open(REPORT_PATH) as f:
        return json.load(f)


# ── Manual retrain trigger ────────────────────────────────────────────────────
@router.post("/retrain")
def trigger_retrain(background_tasks: BackgroundTasks):
    """Admin: trigger a background model retrain without blocking the API."""
    def _run():
        try:
            sys.path.insert(0, _ML_DIR)
            from ml.retrain_scheduler import run_training
            run_training()
        except Exception as e:
            log.error("Manual retrain failed: %s", e)

    background_tasks.add_task(_run)
    return {"status": "retrain_started", "message": "Model retraining in background. Check /api/recommend/report for results."}