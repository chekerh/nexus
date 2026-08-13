"""System info, hardware detection, model recommendations, and setup wizard API."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core import hardware_detector as hw
from ...core.config import settings
from ...core.database import get_db
from ...core.metrics import metrics_endpoint
from ...core.model_router import (
    best_model_for_task,
    refresh_cache,
    system_recommendation,
)
from ...models.user import User
from ..deps import get_current_user

logger = logging.getLogger("nexus.system")
router = APIRouter(tags=["system"])


class WizardCompleteUpdate(BaseModel):
    setup_wizard_complete: bool


class EnvUpdate(BaseModel):
    key: str
    value: str


@router.get("/system/specs")
def get_system_specs(user: User = Depends(get_current_user)):
    """Detect and return hardware specs (RAM, CPU, GPU, Ollama status)."""
    return hw.detect_all()


@router.get("/system/recommendation")
def get_recommendation(user: User = Depends(get_current_user)):
    """Return full system recommendation: hardware + model suggestions + task mapping."""
    try:
        return system_recommendation()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {e}") from e


@router.get("/system/model-for-task/{task}")
def get_model_for_task(task: str, user: User = Depends(get_current_user)):
    """Get the best model for a specific task (strategist, analyst, caption_style, etc)."""
    valid_tasks = ["strategist", "analyst", "caption_style", "virality", "translation", "thumbnails", "chat"]
    if task not in valid_tasks:
        raise HTTPException(status_code=400, detail=f"Invalid task. Choose from: {', '.join(valid_tasks)}")
    try:
        return best_model_for_task(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/system/refresh")
def refresh_system_cache(user: User = Depends(get_current_user)):
    """Force re-detect hardware and installed models."""
    refresh_cache()
    return {"status": "refreshed"}


@router.get("/system/setup-status")
def get_setup_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return whether the setup wizard has been completed."""
    from ...core.database import _ensure_column

    _ensure_column(db, "users", "setup_wizard_complete", "BOOLEAN")

    return {
        "setup_wizard_complete": getattr(user, "setup_wizard_complete", False),
        "dynamic_model_selection": settings.DYNAMIC_MODEL_SELECTION,
    }


@router.post("/system/setup-complete")
def mark_setup_complete(
    payload: WizardCompleteUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark setup wizard as complete for the current user."""
    from ...core.database import _ensure_column

    _ensure_column(db, "users", "setup_wizard_complete", "BOOLEAN")

    user.setup_wizard_complete = payload.setup_wizard_complete
    db.commit()
    return {"status": "updated", "setup_wizard_complete": user.setup_wizard_complete}


@router.get("/system/ollama-models")
def list_ollama_models(user: User = Depends(get_current_user)):
    """List all models currently available in Ollama."""
    return {"models": hw.detect_ollama_models()}


@router.post("/csp-violation-report")
async def csp_report(request: Request):
    """Receive CSP violation reports (called by browser when CSP is violated)."""
    try:
        body = await request.json()
        logger.warning("CSP violation: %s", json.dumps(body, default=str))
    except Exception as exc:
        logger.debug("CSP report parse error: %s", exc)
    return PlainTextResponse("OK", status_code=200)


@router.get("/system/check")
def quick_health_check():
    """Quick system health check (no auth required)."""
    ollama_ok = hw.detect_ollama_running()
    ffmpeg_ok = hw.detect_ffmpeg()
    ram = hw.detect_ram_gb()
    return {
        "status": "ok",
        "ollama_running": ollama_ok,
        "ffmpeg_installed": ffmpeg_ok,
        "ram_gb": ram,
        "ram_tier": hw._ram_tier(ram) if hasattr(hw, "_ram_tier") else "unknown",
    }


@router.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics (no auth required for scraping)."""
    return metrics_endpoint()
