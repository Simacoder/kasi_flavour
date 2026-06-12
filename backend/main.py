"""
Kasi Flavour – FastAPI Backend Entry Point
==========================================
Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import sys, os

# ── Make sure the project root AND ml/ are importable ────────────────────────
_backend_dir  = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_backend_dir, ".."))

for _p in [_backend_dir, _project_root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import orders, menus, users, tracking, recommend, auth

# ── Create all tables on startup ──────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Kasi Flavour API",
    description="Connecting local cooks, drivers & customers across South Africa",
    version="1.0.0",
)

# ── CORS – allow the frontend origin ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(users.router,     prefix="/api/users",     tags=["Users"])
app.include_router(menus.router,     prefix="/api/menus",     tags=["Menus"])
app.include_router(orders.router,    prefix="/api/orders",    tags=["Orders"])
app.include_router(tracking.router,  prefix="/api/track",     tags=["Tracking"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["ML"])

# ── Optionally serve frontend if folder exists ────────────────────────────────
_frontend = os.path.join(_project_root, "frontend")
if os.path.isdir(_frontend):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=_frontend), name="frontend")


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": "Kasi Flavour"}