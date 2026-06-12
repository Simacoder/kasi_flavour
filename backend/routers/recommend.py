"""
routers/recommend.py – Serve ML-powered meal recommendations
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.schemas import RecommendRequest, RecommendOut
from ml.recommend import get_recommendations

router = APIRouter()


@router.post("/", response_model=List[RecommendOut])
def recommend(body: RecommendRequest, db: Session = Depends(get_db)):
    """
    Return top-5 meal recommendations for a user.
    Combines collaborative filtering, content-based, and contextual signals.
    """
    try:
        results = get_recommendations(
            user_id = body.user_id,
            budget  = body.budget,
            lat     = body.lat,
            lng     = body.lng,
            db      = db,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
