"""Nexus-UGC: AI-powered UGC production system.

FastAPI application entry point. Mounts the v1 API, legacy API, and frontend.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from .core.config import settings
from .core.database import init_db
from .api.v1.router import router as v1_router
from .services.job_queue import job_queue
from .services.billing import HAS_STRIPE

app = FastAPI(
    title="Nexus-UGC",
    version="2.0.0",
    description="AI-powered UGC production system — local or cloud.",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount generated clips
CLIPS_DIR = os.path.join(settings.UPLOAD_DIR, "clips")
os.makedirs(CLIPS_DIR, exist_ok=True)
app.mount("/video_clips", StaticFiles(directory=CLIPS_DIR), name="clips")

# API v1
app.include_router(v1_router)


@app.on_event("startup")
async def startup():
    init_db()

    # Import here to avoid circular imports
    from .workers.pipeline import run_pipeline

    job_queue.set_pipeline_runner(run_pipeline)
    job_queue.start_worker()

    backend = (settings.ANALYSIS_BACKEND or "ollama").strip().lower()
    if backend == "airllm" and settings.AIRLLM_WARM_ON_START:
        from .core.airllm_service import airllm_service
        ok, message = airllm_service.ensure_loaded()
        print(f"[startup] airllm warmup: {'ready' if ok else 'fallback-to-ollama'} | {message}")

    print(f"[startup] Stripe: {'connected' if HAS_STRIPE else 'not configured (local mode)'}")


@app.on_event("shutdown")
async def shutdown():
    job_queue.stop_worker()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# Serve frontend (must be last to not catch API routes)
FRONTEND_DIR = settings.FRONTEND_DIR
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
