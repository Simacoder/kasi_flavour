"""
Kasi Flavour – FastAPI Backend Entry Point
==========================================
Run (from inside backend/):
    uvicorn main:app --reload --port 8000

Production:
    gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000

Docs:
    http://localhost:8000/docs

Project layout:
    kasi_flavour/
    ├── backend/        ← run uvicorn from here
    │   ├── main.py
    │   ├── database.py
    │   ├── routers/
    │   ├── models/
    │   ├── schemas/
    │   └── uploads/meals/
    ├── frontend/       ← HTML files at root level (not inside pages/)
    │   ├── index.html
    │   ├── login.html
    │   ├── admin.html
    │   ├── orders.html
    │   ├── seller.html
    │   ├── track.html
    │   ├── css/main.css
    │   ├── js/api.js
    │   ├── js/cart.js
    │   ├── js/menus.js
    │   ├── images/
    │   └── service-worker.js
    └── ml/
        ├── recommend.py
        ├── train.py
        └── retrain_scheduler.py

STEP 1 — move HTML files out of pages/ (run once in PowerShell):
    Move-Item frontend\pages\*.html frontend\

STEP 2 — update all href/src references in HTML files from:
    "../css/main.css"  →  "./css/main.css"
    "../js/api.js"     →  "./js/api.js"
    "orders.html"      →  stays the same (relative links work fine)
"""

import sys, os
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_backend_dir  = Path(__file__).resolve().parent          # .../kasi_flavour/backend
_project_root = _backend_dir.parent                      # .../kasi_flavour
_ml_dir       = _project_root / "ml"
_frontend_dir = _project_root / "frontend"

for _p in [str(_backend_dir), str(_project_root), str(_ml_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── FastAPI + middleware ───────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ── DB ────────────────────────────────────────────────────────────────────────
from database import engine, Base
from routers import auth, users, menus, orders, tracking, recommend

# ── ML scheduler (graceful — skips if ml/ not set up yet) ────────────────────
try:
    from retrain_scheduler import lifespan
    _has_scheduler = True
except ImportError:
    lifespan = None
    _has_scheduler = False

# ── Create DB tables ──────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "Kasi Flavour API",
    description = "Connecting local cooks, drivers & customers across South Africa",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials must be False when allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ══════════════════════════════════════════════════════════════════════════════
#  API ROUTES  — registered FIRST so they always take priority over frontend
# ══════════════════════════════════════════════════════════════════════════════
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(users.router,     prefix="/api/users",     tags=["Users"])
app.include_router(menus.router,     prefix="/api/menus",     tags=["Menus"])
app.include_router(orders.router,    prefix="/api/orders",    tags=["Orders"])
app.include_router(tracking.router,  prefix="/api/track",     tags=["Tracking"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["ML"])


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status":       "ok",
        "app":          "Kasi Flavour",
        "version":      "1.0.0",
        "ml_scheduler": _has_scheduler,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  STATIC MOUNTS  — after API routes
# ══════════════════════════════════════════════════════════════════════════════

# Uploaded meal images → GET /uploads/meals/<filename>
_uploads_dir = _backend_dir / "uploads"
(_uploads_dir / "meals").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


# ══════════════════════════════════════════════════════════════════════════════
#  FRONTEND  — FastAPI 0.139+ app.frontend()
#
#  Serves the entire frontend/ directory.
#  HTML files must be at the root of frontend/ (not inside pages/).
#  Run this once to move them:
#      Move-Item frontend\pages\*.html frontend\
#
#  Route mapping:
#      GET /               → frontend/index.html
#      GET /login.html     → frontend/login.html
#      GET /admin.html     → frontend/admin.html
#      GET /orders.html    → frontend/orders.html
#      GET /seller.html    → frontend/seller.html
#      GET /track.html     → frontend/track.html
#      GET /css/main.css   → frontend/css/main.css
#      GET /js/api.js      → frontend/js/api.js
#      GET /images/...     → frontend/images/...
#
#  fallback="index.html" — serves index.html for unknown browser paths
#  (safe: /api/... and /uploads/... take priority as registered above)
#
#  check_dir=False — skips the existence check at startup so uvicorn
#  still starts even if the frontend/ folder is temporarily missing.
# ══════════════════════════════════════════════════════════════════════════════

if _frontend_dir.is_dir():
    app.frontend(
        "/",
        directory = str(_frontend_dir),
        fallback  = "index.html",
    )
else:
    # Frontend not found — log a warning but don't crash
    import logging
    logging.getLogger(__name__).warning(
        "frontend/ directory not found at %s — "
        "API still running, frontend will return 404.",
        _frontend_dir,
    )
