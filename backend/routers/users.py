"""
routers/users.py – User profile management
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.models import User
from schemas.schemas import UserOut

router = APIRouter()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}/location")
def update_location(user_id: int, lat: float, lng: float, db: Session = Depends(get_db)):
    """Update the user's last known GPS location."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.lat = lat
    user.lng = lng
    db.commit()
    return {"status": "location updated"}
