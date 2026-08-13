"""Pipeline API — upload, process, cancel, status."""

import asyncio
import json
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.drive_downloader import extract_drive_file_id
from ...core.i18n import _
from ...core.translator import is_supported_language
from ...models.job import Job
from ...models.user import User
from ...services.job_queue import job_queue
from ...services.usage import check_usage_quota, get_tier_limits, increment_usage
from ..deps import get_optional_user

router = APIRouter(tags=["pipeline"])

ANONYMOUS_EMAIL = "anonymous@local.dev"


def _resolve_user(db: Session, user: User | None) -> User:
    """Require an authenticated user — no anonymous auto-creation."""
    if not user:
        raise HTTPException(status_code=401, detail=_("error.auth-required"))
    return user


ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}
ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
    "video/x-m4v",
    "video/x-flv",
}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


VALID_ASPECT_RATIOS = {"source", "vertical_9_16", "square_1_1", "portrait_4_5", "landscape_16_9"}


class DriveProcessRequest(BaseModel):
    drive_url: str
    language: str = "en"
    aspect_ratio: str = "vertical_9_16"


# Magic byte signatures for common video formats
VIDEO_SIGNATURES = {
    b"\x66\x74\x79\x70": "mp4",  # ftyp atom in MP4
    b"\x1a\x45\xdf\xa3": "webm/mkv",  # Matroska
    b"\x2e\x52\x4d\x46": "rm",  # RealMedia
    b"\x00\x00\x01\xba": "mpeg",  # MPEG
    b"\x00\x00\x01\xb3": "mpeg",  # MPEG
    b"\x52\x49\x46\x46": "avi",  # AVI (RIFF)
}

MAX_HEADER_BYTES = 64


def _detect_video_type(data: bytes) -> str | None:
    """Detect video format from magic bytes (search within first 64 bytes)."""
    for sig, fmt in VIDEO_SIGNATURES.items():
        if sig in data:
            return fmt
    return None


def _validate_video_file(filename: str, content_type: str, header_bytes: bytes | None = None) -> tuple[bool, str]:
    ext = os.path.splitext((filename or "").lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    if "/" in filename or "\\" in filename or ".." in filename:
        return False, "Path traversal detected"
    if header_bytes:
        detected = _detect_video_type(header_bytes)
        if not detected:
            return False, "File content does not match a known video format"
    return True, ""


@router.post("/process")
async def process_video(
    file: UploadFile = File(...),
    endscreen_image: UploadFile = None,
    cta_text: str = Form("Link in bio to try it free."),
    language: str = Form("en"),
    aspect_ratio: str = Form("vertical_9_16"),
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user = _resolve_user(db, user)
    header_bytes = await file.read(MAX_HEADER_BYTES)
    valid, err = _validate_video_file(file.filename or "", file.content_type or "", header_bytes)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    ok, msg = check_usage_quota(user)
    if not ok:
        raise HTTPException(status_code=402, detail=msg)

    get_tier_limits(user.subscription_tier)
    process_id = str(uuid.uuid4())
    safe_name = os.path.basename(file.filename or "video.mp4")
    video_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_{safe_name}")

    written = 0
    file.file.seek(0)
    with open(video_path, "wb") as buf:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_FILE_SIZE:
                buf.close()
                os.remove(video_path)
                raise HTTPException(status_code=400, detail=_("error.file-too-large"))
            buf.write(chunk)

    endscreen_path = None
    if endscreen_image:
        img_bytes = await endscreen_image.read(512)
        endscreen_image.file.seek(0)
        img_type = _detect_image_type(img_bytes)
        if img_type not in ("jpeg", "png", "gif", "webp") and img_type is not None:
            raise HTTPException(status_code=400, detail=_("error.invalid-image-format"))
        img_name = os.path.basename(endscreen_image.filename or "endscreen.jpg")
        endscreen_ext = os.path.splitext(img_name)[1].lower()
        if endscreen_ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            raise HTTPException(status_code=400, detail=_("error.invalid-image-extension"))
        endscreen_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_endscreen_{img_name}")
        img_size = 0
        with open(endscreen_path, "wb") as buf:
            while chunk := endscreen_image.file.read(1024 * 1024):
                img_size += len(chunk)
                if img_size > 10 * 1024 * 1024:
                    buf.close()
                    os.remove(endscreen_path)
                    raise HTTPException(status_code=400, detail=_("error.endscreen-too-large"))
                buf.write(chunk)

    target_lang = language if is_supported_language(language) else "en"
    ar = aspect_ratio if aspect_ratio in VALID_ASPECT_RATIOS else "vertical_9_16"
    job_id = job_queue.enqueue(
        db,
        user.id,
        filename=file.filename,
        video_path=video_path,
        endscreen_path=endscreen_path or "",
        cta_text=cta_text or "Link in bio to try it free.",
        target_language=target_lang,
        aspect_ratio=ar,
    )

    increment_usage(user, db)

    return {"process_id": job_id}


@router.post("/process-drive")
async def process_drive_video(
    payload: DriveProcessRequest,
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user = _resolve_user(db, user)
    ok, msg = check_usage_quota(user)
    if not ok:
        raise HTTPException(status_code=402, detail=msg)

    file_id = extract_drive_file_id(payload.drive_url)
    if not file_id:
        raise HTTPException(status_code=400, detail=_("error.invalid-drive-url"))

    target_lang = payload.language if is_supported_language(payload.language) else "en"
    ar = payload.aspect_ratio if payload.aspect_ratio in VALID_ASPECT_RATIOS else "vertical_9_16"
    job_id = job_queue.enqueue(
        db,
        user.id,
        filename=f"drive_{file_id[:8]}.mp4",
        source="drive",
        drive_url=payload.drive_url,
        target_language=target_lang,
        aspect_ratio=ar,
    )

    increment_usage(user, db)

    return {"process_id": job_id}


@router.post("/cancel/{process_id}")
def cancel_processing(process_id: str, user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = _resolve_user(db, user)
    job = job_queue.get_job(db, process_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail=_("error.process-not-found"))
    if job.status == "completed":
        return {"status": "already_completed"}
    job_queue.cancel_job(db, process_id)
    return {"status": "cancelled"}


@router.get("/status/{process_id}")
def get_status(process_id: str, user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = _resolve_user(db, user)
    job = job_queue.get_job(db, process_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail=_("error.process-not-found"))

    result = {
        "status": job.status,
        "filename": job.filename,
        "language": job.target_language or "en",
        "aspect_ratio": job.aspect_ratio or "vertical_9_16",
        "thinking": json.loads(job.thinking_json or "[]"),
        "error": job.error or None,
        "progress_stage": job.progress_stage or "",
        "progress_percent": job.progress_percent or 0,
        "progress_message": job.progress_message or "",
    }

    if job.status == "completed":
        result.update(
            {
                "transcript": job.transcript,
                "analysis": json.loads(job.analysis_json) if job.analysis_json else None,
                "clips": json.loads(job.clips_json) if job.clips_json else [],
                "timing": {
                    "transcription_seconds": job.timing_transcription,
                    "analysis_seconds": job.timing_analysis,
                    "cutting_seconds": job.timing_cutting,
                    "total_seconds": job.timing_total,
                },
            }
        )

    return result


@router.get("/jobs")
def list_jobs(user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = _resolve_user(db, user)
    jobs = job_queue.get_user_jobs(db, user.id)
    return {
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "filename": j.filename,
                "source": j.source,
                "language": j.target_language or "en",
                "aspect_ratio": j.aspect_ratio or "vertical_9_16",
                "error": j.error or None,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    }


def _detect_image_type(data: bytes) -> str | None:
    """Detect image MIME type from magic bytes (replaces deprecated imghdr)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] in (b"\xff\xd8",):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:3] in (b"GIF",):
        return "gif"
    return None


# ── SSE Progress Stream ──
async def _progress_event_generator(job_id: str, user_id: str):
    """Generate SSE events for job progress."""
    from ...core.database import SessionLocal
    from ...models.job import Job

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
        if not job:
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
            return
    finally:
        db.close()

    last_thought_count = 0
    last_stage = ""
    last_percent = -1
    last_message = ""

    while True:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            # Check for new thoughts
            thoughts = json.loads(job.thinking_json or "[]")
            if len(thoughts) > last_thought_count:
                new_thoughts = thoughts[last_thought_count:]
                for thought in new_thoughts:
                    yield f"event: thought\ndata: {json.dumps({'thought': thought})}\n\n"
                last_thought_count = len(thoughts)

            # Check for progress updates
            if job.progress_stage != last_stage:
                last_stage = job.progress_stage
                yield f"event: stage\ndata: {json.dumps({'stage': job.progress_stage})}\n\n"

            if job.progress_percent != last_percent:
                last_percent = job.progress_percent
                yield f"event: progress\ndata: {json.dumps({'percent': job.progress_percent})}\n\n"

            if job.progress_message != last_message:
                last_message = job.progress_message
                yield f"event: message\ndata: {json.dumps({'message': job.progress_message})}\n\n"

            # Check if job is done
            if job.status in ("completed", "failed", "cancelled"):
                final_data = {
                    "status": job.status,
                    "error": job.error if job.status == "failed" else None,
                }
                if job.status == "completed":
                    final_data.update(
                        {
                            "transcript": job.transcript,
                            "analysis": json.loads(job.analysis_json) if job.analysis_json else None,
                            "clips": json.loads(job.clips_json) if job.clips_json else [],
                            "timing": {
                                "transcription_seconds": job.timing_transcription,
                                "analysis_seconds": job.timing_analysis,
                                "cutting_seconds": job.timing_cutting,
                                "total_seconds": job.timing_total,
                            },
                        }
                    )
                yield f"event: done\ndata: {json.dumps(final_data)}\n\n"
                break

            # Heartbeat
            yield f"event: heartbeat\ndata: {json.dumps({'status': job.status})}\n\n"

        finally:
            db.close()

        await asyncio.sleep(1)

    # Send final close event
    yield f"event: close\ndata: {json.dumps({})}\n\n"


@router.get("/stream/{process_id}")
async def stream_progress(process_id: str, user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Server-Sent Events stream for real-time job progress."""
    user = _resolve_user(db, user)

    # Verify job exists and belongs to user
    job = db.query(Job).filter(Job.id == process_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail=_("error.process-not-found"))

    return StreamingResponse(
        _progress_event_generator(process_id, user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
