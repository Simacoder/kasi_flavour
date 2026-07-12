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
import logging
from pathlib import Path

# ── Logging ─────────────────────────────────────────────────────────────────
# Configured early so startup messages (DB connection, scheduler, frontend)
# are actually visible in FastAPI Cloud's runtime logs.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("kasi_flavour")

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
# FIX: This used to run unguarded at import time. If the DB is unreachable
# (e.g. DATABASE_URL isn't set in the deployment environment and it falls
# back to the localhost default, which doesn't exist in a container), this
# call would hang/raise, the module import would never finish, and uvicorn
# would never come up — with no useful error in the build logs.
#
# Now: log clearly on success or failure, and don't let a DB outage take
# the whole app down. /health will still report db_connected so you can see
# the real state at a glance instead of guessing from a dead deployment.
_db_connected = False
try:
    Base.metadata.create_all(bind=engine)
    _db_connected = True
    logger.info("Database tables created/verified successfully.")
except Exception as exc:
    logger.error(
        "Could not connect to database at startup (DATABASE_URL=%s): %s. "
        "App will still start, but DB-backed routes will fail until this is fixed.",
        "SET" if os.getenv("DATABASE_URL") else "NOT SET (using localhost fallback)",
        exc,
    )

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
        "status":        "ok",
        "app":           "Kasi Flavour",
        "version":       "1.0.0",
        "ml_scheduler":  _has_scheduler,
        "db_connected":  _db_connected,  # FIX: now reflects real DB state at startup
    }


# TEMP DIAGNOSTIC — remove once DB connectivity is confirmed working.
# Log streaming wasn't surfacing the startup exception, so this attempts a
# live connection on request and returns the real error directly in the
# response instead, bypassing the logging pipeline entirely.
@app.get("/debug/db", tags=["Health"])
def debug_db():
    import os as _os
    from sqlalchemy import text as _text
    raw_url = _os.getenv("DATABASE_URL", "NOT SET — using localhost fallback")
    # Redact password before returning anything
    safe_url = raw_url
    if "@" in raw_url and "://" in raw_url:
        scheme, rest = raw_url.split("://", 1)
        creds, hostpart = rest.split("@", 1) if "@" in rest else ("", rest)
        user = creds.split(":")[0] if ":" in creds else creds
        safe_url = f"{scheme}://{user}:***REDACTED***@{hostpart}"
    try:
        with engine.connect() as conn:
            conn.execute(_text("SELECT 1"))
        return {"connected": True, "database_url_used": safe_url}
    except Exception as exc:
        return {
            "connected": False,
            "database_url_used": safe_url,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
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
    logger.info("Serving frontend from %s", _frontend_dir)
else:
    # Frontend not found — log a warning but don't crash
    logger.warning(
        "frontend/ directory not found at %s — "
        "API still running, frontend will return 404.",
        _frontend_dir,
    )