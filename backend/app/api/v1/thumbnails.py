"""Thumbnail API — generate, list, serve, track A/B impressions/clicks."""

import json
import os
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.ab_testing import compute_ab_stats, declare_winner, record_click, record_impression
from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...core.thumbnails import generate_thumbnails
from ...models.job import Job
from ...models.thumbnail import Thumbnail
from ...models.user import User
from ..deps import get_current_user, get_optional_user

router = APIRouter(tags=["thumbnails"])


def _resolve_user(db: Session, user: User | None) -> User:
    if not user:
        raise HTTPException(status_code=401, detail=_("error.auth-required"))
    return user


class GenerateRequest(BaseModel):
    title: str = ""
    clip_index: int = 0
    count: int = 4


@router.post("/jobs/{job_id}/thumbnails")
def generate_job_thumbnails(
    job_id: str,
    payload: GenerateRequest,
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user = _resolve_user(db, user)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail=_("error.job-not-found"))
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=_("error.job-not-completed"))

    hooks = json.loads(cast(str, job.analysis_json or "{}")).get("hooks", []) if job.analysis_json else []
    if not hooks:
        raise HTTPException(status_code=400, detail=_("error.job-no-clips"))

    clip_names = json.loads(cast(str, job.clips_json)) if job.clips_json else []
    if not clip_names:
        raise HTTPException(status_code=400, detail=_("error.job-no-clips"))

    clip_idx = max(0, min(payload.clip_index, len(hooks) - 1))
    clips_dir = os.path.join(settings.UPLOAD_DIR, "clips")

    frame_source: str = cast(str, job.video_path) or ""
    if clip_idx < len(clip_names):
        candidate = os.path.join(clips_dir, clip_names[clip_idx])
        if os.path.isfile(candidate):
            frame_source = candidate

    results = generate_thumbnails(
        video_path=frame_source,
        transcript=cast(str, job.transcript or ""),
        hooks=hooks,
        clips_dir=clips_dir,
        clip_index=clip_idx,
        title=payload.title,
    )

    # Save to database
    thumbnails_created = []
    for r in results[: payload.count]:
        thumb = Thumbnail(
            job_id=job.id,
            clip_index=clip_idx,
            variant_name=r["variant_name"],
            image_path=r["image_path"],
            title_overlay=r["title_overlay"],
            layout=r["layout"],
            score=r["score"],
        )
        db.add(thumb)
        db.flush()
        thumbnails_created.append(
            {
                "id": thumb.id,
                "variant_name": thumb.variant_name,
                "title_overlay": thumb.title_overlay,
                "layout": thumb.layout,
                "score": thumb.score,
                "url": f"/api/v1/thumbnails/{thumb.id}/image",
            }
        )

    db.commit()

    return {"thumbnails": thumbnails_created}


@router.get("/jobs/{job_id}/thumbnails")
def list_job_thumbnails(
    job_id: str,
    clip_index: int | None = None,
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user = _resolve_user(db, user)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail=_("error.job-not-found"))

    query = db.query(Thumbnail).filter(Thumbnail.job_id == job_id)
    if clip_index is not None:
        query = query.filter(Thumbnail.clip_index == clip_index)
    thumbnails = query.order_by(Thumbnail.clip_index, Thumbnail.score.desc()).all()

    return {
        "thumbnails": [
            {
                "id": t.id,
                "clip_index": t.clip_index,
                "variant_name": t.variant_name,
                "title_overlay": t.title_overlay,
                "layout": t.layout,
                "score": t.score,
                "impressions": t.impressions or 0,
                "clicks": t.clicks or 0,
                "is_winner": t.is_winner or False,
                "url": f"/api/v1/thumbnails/{t.id}/image",
            }
            for t in thumbnails
        ]
    }


@router.get("/thumbnails/{thumbnail_id}/image")
def serve_thumbnail_image(
    thumbnail_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thumb = db.query(Thumbnail).filter(Thumbnail.id == thumbnail_id).first()
    if not thumb or not thumb.image_path:
        raise HTTPException(status_code=404, detail=_("error.thumbnail-not-found"))
    if not user.is_admin:
        job = db.query(Job).filter(Job.id == thumb.job_id).first()
        if not job or job.user_id != user.id:
            raise HTTPException(status_code=403, detail=_("error.thumbnail-not-authorized"))
    full = os.path.abspath(thumb.image_path)
    if not full.startswith(os.path.abspath(settings.UPLOAD_DIR) + os.sep):
        raise HTTPException(status_code=400, detail=_("error.invalid-path"))
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail=_("error.image-file-not-found"))
    return FileResponse(full, media_type="image/jpeg")


@router.post("/thumbnails/{thumbnail_id}/impression")
def track_impression(
    thumbnail_id: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    ok = record_impression(db, thumbnail_id)
    if not ok:
        raise HTTPException(status_code=404, detail=_("error.thumbnail-not-found"))
    return {"ok": True}


@router.post("/thumbnails/{thumbnail_id}/click")
def track_click(
    thumbnail_id: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    ok = record_click(db, thumbnail_id)
    if not ok:
        raise HTTPException(status_code=404, detail=_("error.thumbnail-not-found"))
    return {"ok": True}


@router.get("/thumbnails/{thumbnail_id}/stats")
def thumbnail_stats(
    thumbnail_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thumb = db.query(Thumbnail).filter(Thumbnail.id == thumbnail_id).first()
    if not thumb:
        raise HTTPException(status_code=404, detail=_("error.thumbnail-not-found"))

    # Get all variants for this job+clip for comparison
    siblings = (
        db.query(Thumbnail)
        .filter(
            Thumbnail.job_id == thumb.job_id,
            Thumbnail.clip_index == thumb.clip_index,
        )
        .all()
    )

    stats = compute_ab_stats(siblings)
    return {"stats": stats}


@router.post("/thumbnails/{thumbnail_id}/declare-winner")
def declare_thumbnail_winner(
    thumbnail_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = declare_winner(db, thumbnail_id)
    if not ok:
        raise HTTPException(status_code=404, detail=_("error.thumbnail-not-found"))
    return {"ok": True}
