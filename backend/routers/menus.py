"""
routers/menus.py – Browse menus, flash deals, cook profiles
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db
from models.models import MenuItem, Cook
from schemas.schemas import MenuItemCreate, MenuItemOut

router = APIRouter()


@router.get("/", response_model=List[MenuItemOut])
def list_menus(
    kasi:  Optional[str]  = None,
    tag:   Optional[str]  = None,
    flash: bool           = False,
    db:    Session        = Depends(get_db)
):
    """Browse all available menu items, optionally filtered by kasi or tag."""
    q = db.query(MenuItem).filter(MenuItem.available == True)
    if flash:
        now = datetime.utcnow()
        q = q.filter(MenuItem.is_flash_deal == True, MenuItem.flash_expires > now)
    if kasi:
        q = q.join(Cook).filter(Cook.kasi.ilike(f"%{kasi}%"))
    if tag:
        q = q.filter(MenuItem.cuisine_tags.ilike(f"%{tag}%"))
    return q.all()


@router.get("/{item_id}", response_model=MenuItemOut)
def get_menu_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item


@router.post("/", response_model=MenuItemOut, status_code=201)
def create_menu_item(
    body:    MenuItemCreate,
    cook_id: int,            # replace with JWT cook id
    db:      Session = Depends(get_db)
):
    item = MenuItem(**body.model_dump(), cook_id=cook_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_menu_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(item)
    db.commit()
