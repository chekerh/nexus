"""Brain Rot Shorts Generator API — generate scripts, render videos, publish to Shorts."""

import logging
import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...models.persona import Persona, Post
from ...models.user import User
from ...services.brainrot import CAPTION_STYLES, CAPTION_STYLES_META, NICHES, generate_script, render_brainrot_video
from ..deps import get_current_user

logger = logging.getLogger("nexus.brainrot.api")
router = APIRouter(tags=["brainrot"])


class GenerateRequest(BaseModel):
    niche: str = "drama"
    idea: str = ""
    caption_style: str = "brain_rot"
    language: str = "en"


class RenderRequest(BaseModel):
    niche: str = "drama"
    idea: str = ""
    caption_style: str = "brain_rot"
    background_video: str = ""
    language: str = "en"


class PublishRequest(BaseModel):
    niche: str = "drama"
    idea: str = ""
    caption_style: str = "brain_rot"
    title: str = ""
    persona_id: str = ""
    platform: str = "youtube"
    schedule_at: str = ""
    background_video: str = ""
    language: str = "en"


@router.get("/brainrot/niches")
def list_niches():
    """List available brain rot niches and caption styles."""
    return {
        "niches": list(NICHES.keys()),
        "caption_styles": list(CAPTION_STYLES.keys()),
    }


@router.get("/brainrot/styles")
def list_caption_styles():
    """Return full caption style metadata (labels, descriptions, etc.) for frontend."""
    return {"styles": CAPTION_STYLES_META}


@router.post("/brainrot/generate")
def generate_brainrot(payload: GenerateRequest, user: User = Depends(get_current_user)):
    """Generate a brain rot short script."""
    if payload.niche not in NICHES:
        raise HTTPException(
            status_code=400, detail=_("error.unknown-niche").format(niche=payload.niche, available=list(NICHES.keys()))
        )
    if payload.caption_style not in CAPTION_STYLES:
        raise HTTPException(status_code=400, detail=_("error.unknown-style").format(style=payload.caption_style))

    result = generate_script(payload.niche, payload.idea, payload.caption_style, payload.language)
    return result


@router.post("/brainrot/upload-background")
async def upload_background(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Upload a background video for brain rot renders."""
    if not file.filename:
        raise HTTPException(status_code=400, detail=_("error.no-file-provided"))

    allowed = (".mp4", ".mov", ".avi", ".webm", ".mkv")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400, detail=_("error.unsupported-format").format(ext=ext, allowed=", ".join(allowed))
        )

    # Validate first bytes match a known video format
    from .pipeline import _detect_video_type

    header = await file.read(64)
    if not _detect_video_type(header):
        raise HTTPException(status_code=400, detail=_("error.unknown-video-format"))
    file.file.seek(0)

    # Stream file to disk with size limit
    import shutil
    import tempfile

    max_size = 500 * 1024 * 1024
    written = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        with tmp:
            while chunk := await file.read(64 * 1024):
                written += len(chunk)
                if written > max_size:
                    raise HTTPException(
                        status_code=400, detail=_("error.file-too-large-max").format(max_size=max_size // (1024 * 1024))
                    )
                tmp.write(chunk)

        bg_dir = os.path.join(settings.UPLOAD_DIR, "backgrounds")
        os.makedirs(bg_dir, exist_ok=True)
        filename = f"bg_{uuid.uuid4().hex[:12]}{ext}"
        dest = os.path.join(bg_dir, filename)
        shutil.move(tmp.name, dest)
    except Exception:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise

    return {"filename": filename, "path": dest, "url": f"/api/v1/media/backgrounds/{filename}"}


@router.post("/brainrot/render")
def render_brainrot(payload: RenderRequest, user: User = Depends(get_current_user)):
    """Generate script + render video."""
    if payload.niche not in NICHES:
        raise HTTPException(status_code=400, detail=_("error.unknown-niche-simple").format(niche=payload.niche))

    script = generate_script(payload.niche, payload.idea, payload.caption_style, payload.language)
    clips_dir = os.path.join(settings.UPLOAD_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    filename = f"brainrot_{user.id[:8]}_{int(datetime.now(UTC).timestamp())}.mp4"
    output_path = os.path.join(clips_dir, filename)

    success = render_brainrot_video(script, output_path, payload.background_video)
    if not success:
        raise HTTPException(status_code=500, detail=_("error.video-render-failed"))

    return {
        "script": script,
        "video_url": f"/api/v1/media/clips/{filename}",
        "filename": filename,
    }


@router.post("/brainrot/publish")
def publish_brainrot(payload: PublishRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate script → render video → create post → publish in one shot."""
    if payload.niche not in NICHES:
        raise HTTPException(status_code=400, detail=_("error.unknown-niche-simple").format(niche=payload.niche))

    # 1. Generate script
    script = generate_script(payload.niche, payload.idea, payload.caption_style, payload.language)

    # 2. Render video
    clips_dir = os.path.join(settings.UPLOAD_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    filename = f"brainrot_{user.id[:8]}_{int(datetime.now(UTC).timestamp())}.mp4"
    output_path = os.path.join(clips_dir, filename)

    success = render_brainrot_video(script, output_path, payload.background_video)
    if not success:
        raise HTTPException(status_code=500, detail=_("error.video-render-failed"))

    # 3. Find or create a persona for brain rot content
    persona_name = f"Brain Rot - {payload.niche}"
    persona = (
        db.query(Persona)
        .filter(
            Persona.user_id == user.id,
            Persona.name == persona_name,
        )
        .first()
    )
    if not persona:
        persona = Persona(
            user_id=user.id,
            name=persona_name,
            bio=f"AI-generated {payload.niche} short content",
            target_audience="General",
            is_active=True,
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)

    # 4. Create a post
    title = payload.title.strip() or script.get("hook", f"{payload.niche} short")
    platform = payload.platform if payload.platform in ("youtube", "tiktok") else "youtube"

    post = Post(
        persona_id=persona.id,
        user_id=user.id,
        platform=platform,
        title=title,
        body=script.get("script", ""),
        media_path=output_path,
        status="scheduled" if payload.schedule_at else "pending",
        scheduled_at=datetime.fromisoformat(payload.schedule_at) if payload.schedule_at else None,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return {
        "success": True,
        "post_id": post.id,
        "persona_id": persona.id,
        "title": title,
        "platform": platform,
        "status": post.status,
        "video_url": f"/api/v1/media/clips/{filename}",
        "script": script,
    }
