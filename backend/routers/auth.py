"""
routers/auth.py – Register & Login with JWT
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os

from database import get_db
from models.models import User
from schemas.schemas import RegisterRequest, LoginRequest, TokenResponse

router = APIRouter()

SECRET_KEY  = os.getenv("SECRET_KEY", "kasi-flavour-secret-change-in-prod")
ALGORITHM   = "HS256"
TOKEN_EXPIRY = 60 * 24  # 24 hours in minutes

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = User(
        name     = body.name,
        phone    = body.phone,
        email    = body.email,
        password = hash_password(body.password),
        role     = body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or password"
        )
    token = create_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token}
