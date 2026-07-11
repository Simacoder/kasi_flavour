"""
routers/auth.py – Register & Login with JWT
============================================
Fix: removed passlib (broken with bcrypt >= 4.x on Python 3.11)
     now uses bcrypt directly — no version conflicts.

Install: pip install bcrypt python-jose[cryptography]
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
import bcrypt
import os

from database import get_db
from models.models import User
from schemas.schemas import RegisterRequest, LoginRequest

router = APIRouter()

SECRET_KEY   = os.getenv("SECRET_KEY", "kasi-flavour-secret-change-in-prod")
ALGORITHM    = "HS256"
TOKEN_EXPIRY = 60 * 24   # 24 hours in minutes


# ── Password helpers (bcrypt direct — no passlib) ─────────────────────────────
def hash_password(password: str) -> str:
    """Hash password with bcrypt. Truncates to 72 bytes to avoid ValueError."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt      = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain password against stored bcrypt hash."""
    try:
        pwd_bytes    = plain.encode("utf-8")[:72]
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_token(data: dict) -> str:
    payload        = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

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

    token = create_token({"sub": str(user.id), "role": str(user.role.value)})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role.value,
        "name":         user.name,
    }


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password",
        )
    token = create_token({"sub": str(user.id), "role": str(user.role.value)})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role.value,
        "name":         user.name,
    }
