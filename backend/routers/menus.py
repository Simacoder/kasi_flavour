"""
routers/menus.py – Menu CRUD + image upload
============================================
FIX: /upload-image MUST be declared before /{item_id} otherwise
     FastAPI matches "upload-image" as the item_id path param
     and returns 405 Method Not Allowed on POST.

FIX: images now upload to Backblaze B2 instead of local disk. Local disk
     writes don't survive container redeploys on FastAPI Cloud — every
     redeploy wiped previously uploaded meal photos, causing 404s. See
     storage.py for the B2 client; images are served back through the
     /uploads/meals/{filename} proxy route in main.py (bucket is private).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from jose import jwt, JWTError
import uuid, os

from database import get_db
from models.models import MenuItem, Cook, User
from schemas.schemas import MenuItemCreate, MenuItemOut
from storage import upload_bytes, delete_object

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "kasi-flavour-secret-change-in-prod")
ALGORITHM  = "HS256"


# ── JWT helper ────────────────────────────────────────────────────────────────
def _get_user_id(authorization: str = "") -> Optional[int]:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub", 0)) or None
    except JWTError:
        return None


def _resolve_cook(user_id: int, db: Session) -> Cook:
    """Get or auto-create a Cook record for this user."""
    cook = db.query(Cook).filter(Cook.user_id == user_id).first()
    if not cook:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        cook = Cook(user_id=user_id, kasi="", bio="", rating=0.0, badges="")
        db.add(cook)
        db.commit()
        db.refresh(cook)
    return cook


# ══════════════════════════════════════════════════════════════════════════════
# IMPORTANT: all fixed-path routes (/upload-image, /) MUST come BEFORE
# the wildcard route (/{item_id}) — otherwise FastAPI greedily matches
# "upload-image" as an item_id and returns 405.
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Image upload  POST /api/menus/upload-image ─────────────────────────────
@router.post("/upload-image")
async def upload_meal_image(
    file:          UploadFile = File(...),
    authorization: str        = Header(default=""),
):
    """
    Upload a meal photo. Call this first, get back image_url,
    then include image_url when POSTing to /api/menus/.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 5 MB")

    ext      = (file.filename or "img").rsplit(".", 1)[-1].lower()
    ext      = ext if ext in {"jpg", "jpeg", "png", "webp", "gif"} else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"

    try:
        upload_bytes(
            key=f"meals/{filename}",
            data=contents,
            content_type=file.content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {exc}")

    # URL scheme unchanged from before — frontend still requests
    # /uploads/meals/<filename>, which main.py now proxies from B2.
    return {"image_url": f"/uploads/meals/{filename}"}


# ── 2. List all menus  GET /api/menus/ ────────────────────────────────────────
@router.get("/", response_model=List[MenuItemOut])
def list_menus(
    kasi:  Optional[str] = None,
    tag:   Optional[str] = None,
    flash: bool          = False,
    db:    Session       = Depends(get_db),
):
    q = db.query(MenuItem).filter(MenuItem.available == True)
    if flash:
        now = datetime.utcnow()
        q   = q.filter(
            MenuItem.is_flash_deal == True,
            MenuItem.flash_expires  > now,
        )
    if kasi:
        q = q.join(Cook).filter(Cook.kasi.ilike(f"%{kasi}%"))
    if tag:
        q = q.filter(MenuItem.cuisine_tags.ilike(f"%{tag}%"))
    return q.all()


# ── 3. Create menu item  POST /api/menus/ ─────────────────────────────────────
@router.post("/", response_model=MenuItemOut, status_code=201)
def create_menu_item(
    body:          MenuItemCreate,
    authorization: str     = Header(default=""),
    db:            Session = Depends(get_db),
):
    """cook_id is resolved from JWT — no need to pass it in the URL."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    cook = _resolve_cook(user_id, db)

    item = MenuItem(
        cook_id       = cook.id,
        name          = body.name,
        description   = body.description,
        price         = body.price,
        cuisine_tags  = body.cuisine_tags,
        image_url     = body.image_url,
        is_flash_deal = body.is_flash_deal,
        flash_price   = body.flash_price,
        available     = True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ── 4. Get single item  GET /api/menus/{item_id} ──────────────────────────────
# NOTE: This wildcard route is LAST so it never shadows the routes above.
@router.get("/{item_id}", response_model=MenuItemOut)
def get_menu_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item


# ── 5. Toggle availability  PATCH /api/menus/{item_id} ────────────────────────
@router.patch("/{item_id}")
def update_menu_item(
    item_id:   int,
    available: Optional[bool] = None,
    db:        Session        = Depends(get_db),
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    if available is not None:
        item.available = available
    db.commit()
    return {"id": item.id, "available": item.available}


# ── 6. Delete item  DELETE /api/menus/{item_id} ───────────────────────────────
@router.delete("/{item_id}", status_code=204)
def delete_menu_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    if item.image_url:
        filename = item.image_url.rsplit("/", 1)[-1]
        delete_object(f"meals/{filename}")
    db.delete(item)
    db.commit()