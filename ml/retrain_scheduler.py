"""
ml/retrain_scheduler.py – Auto-retrain trigger for Kasi Flavour
===============================================================
Wires into FastAPI's lifespan to retrain the model:
  • On server startup  (if model.pkl is missing or > 24h old)
  • Every 24 hours in background

Usage in main.py:
    from ml.retrain_scheduler import lifespan
    app = FastAPI(lifespan=lifespan, ...)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

log        = logging.getLogger(__name__)
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
RETRAIN_INTERVAL_HOURS = 24


def _model_is_stale() -> bool:
    """True if model.pkl is missing or older than RETRAIN_INTERVAL_HOURS."""
    if not os.path.exists(MODEL_PATH):
        return True
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(MODEL_PATH))
    return age > timedelta(hours=RETRAIN_INTERVAL_HOURS)


def run_training():
    """Run train.py synchronously (called from a thread pool)."""
    try:
        import sys
        _ml_dir = os.path.dirname(os.path.abspath(__file__))
        _backend = os.path.join(_ml_dir, "..", "backend")
        for p in [_ml_dir, _backend]:
            if p not in sys.path:
                sys.path.insert(0, p)

        from database import SessionLocal
        from ml.train import train

        db = SessionLocal()
        try:
            report = train(db)
            log.info("Auto-retrain complete. Precision@5=%.4f",
                     report["top_n_metrics"].get("precision@5", 0))
        finally:
            db.close()
    except Exception as e:
        log.error("Auto-retrain failed: %s", e)


async def _retrain_loop():
    """Background coroutine: retrain every RETRAIN_INTERVAL_HOURS."""
    while True:
        await asyncio.sleep(RETRAIN_INTERVAL_HOURS * 3600)
        log.info("Scheduled auto-retrain triggered")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_training)


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan context manager — replaces @app.on_event."""
    # Startup
    if _model_is_stale():
        log.info("Model missing or stale → triggering background retrain on startup")
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, run_training)

    # Launch periodic retrain
    task = asyncio.create_task(_retrain_loop())

    yield  # App runs here

    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    log.info("Retrain scheduler stopped")