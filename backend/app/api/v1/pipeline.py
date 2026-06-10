"""Pipeline API — upload, process, cancel, status."""
import json
import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.config import settings
from ...core.drive_downloader import download_drive_file, extract_drive_file_id
from ...models.user import User, SubscriptionTier
from ...models.job import Job
from ...services.job_queue import job_queue
from ...services.usage import check_usage_quota, increment_usage, get_tier_limits
from ...core.translator import is_supported_language
from ..deps import get_current_user, get_optional_user

router = APIRouter(tags=["pipeline"])

ANONYMOUS_EMAIL = "anonymous@local.dev"


def _resolve_user(db: Session, user: User | None) -> User:
    """Return user if authenticated, otherwise create/find anonymous user."""
    if user:
        return user
    anon = db.query(User).filter(User.email == ANONYMOUS_EMAIL).first()
    if not anon:
        anon = User(
            email=ANONYMOUS_EMAIL,
            password_hash="",
            display_name="Anonymous",
            subscription_tier=SubscriptionTier.FREE,
        )
        db.add(anon)
        db.commit()
        db.refresh(anon)
    return anon

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}
ALLOWED_MIME_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm", "video/x-m4v", "video/x-flv",
}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


VALID_ASPECT_RATIOS = {"source", "vertical_9_16", "square_1_1", "portrait_4_5", "landscape_16_9"}

class DriveProcessRequest(BaseModel):
    drive_url: str
    language: str = "en"
    aspect_ratio: str = "vertical_9_16"


def _validate_video_file(filename: str, content_type: str) -> tuple[bool, str]:
    ext = os.path.splitext((filename or "").lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    if "/" in filename or "\\" in filename or ".." in filename:
        return False, "Path traversal detected"
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
    valid, err = _validate_video_file(file.filename or "", file.content_type or "")
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    ok, msg = check_usage_quota(db, user)
    if not ok:
        raise HTTPException(status_code=402, detail=msg)

    limits = get_tier_limits(user.subscription_tier)
    process_id = str(uuid.uuid4())
    safe_name = os.path.basename(file.filename or "video.mp4")
    video_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_{safe_name}")

    with open(video_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    if os.path.getsize(video_path) > MAX_FILE_SIZE:
        os.remove(video_path)
        raise HTTPException(status_code=400, detail="File exceeds 2GB limit")

    endscreen_path = None
    if endscreen_image:
        img_name = os.path.basename(endscreen_image.filename or "endscreen.jpg")
        endscreen_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_endscreen_{img_name}")
        with open(endscreen_path, "wb") as buf:
            shutil.copyfileobj(endscreen_image.file, buf)

    target_lang = language if is_supported_language(language) else "en"
    ar = aspect_ratio if aspect_ratio in VALID_ASPECT_RATIOS else "vertical_9_16"
    job_id = job_queue.enqueue(
        db, user.id,
        filename=file.filename,
        video_path=video_path,
        endscreen_path=endscreen_path,
        cta_text=cta_text or "Link in bio to try it free.",
        target_language=target_lang,
        aspect_ratio=ar,
    )

    increment_usage(db, user)

    return {"process_id": job_id}


@router.post("/process-drive")
async def process_drive_video(
    payload: DriveProcessRequest,
    user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user = _resolve_user(db, user)
    ok, msg = check_usage_quota(db, user)
    if not ok:
        raise HTTPException(status_code=402, detail=msg)

    file_id = extract_drive_file_id(payload.drive_url)
    if not file_id:
        raise HTTPException(status_code=400, detail="Invalid Google Drive URL")

    target_lang = payload.language if is_supported_language(payload.language) else "en"
    ar = payload.aspect_ratio if payload.aspect_ratio in VALID_ASPECT_RATIOS else "vertical_9_16"
    job_id = job_queue.enqueue(
        db, user.id,
        filename=f"drive_{file_id[:8]}.mp4",
        source="drive",
        drive_url=payload.drive_url,
        target_language=target_lang,
        aspect_ratio=ar,
    )

    increment_usage(db, user)

    return {"process_id": job_id}


@router.post("/cancel/{process_id}")
def cancel_processing(process_id: str, user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = _resolve_user(db, user)
    job = job_queue.get_job(db, process_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Process not found")
    if job.status == "completed":
        return {"status": "already_completed"}
    job_queue.cancel_job(db, process_id)
    return {"status": "cancelled"}


@router.get("/status/{process_id}")
def get_status(process_id: str, user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = _resolve_user(db, user)
    job = job_queue.get_job(db, process_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Process not found")

    result = {
        "status": job.status,
        "filename": job.filename,
        "language": job.target_language or "en",
        "aspect_ratio": job.aspect_ratio or "vertical_9_16",
        "thinking": json.loads(job.thinking_json or "[]"),
        "error": job.error or None,
    }

    if job.status == "completed":
        result.update({
            "transcript": job.transcript,
            "analysis": json.loads(job.analysis_json) if job.analysis_json else None,
            "clips": json.loads(job.clips_json) if job.clips_json else [],
            "timing": {
                "transcription_seconds": job.timing_transcription,
                "analysis_seconds": job.timing_analysis,
                "cutting_seconds": job.timing_cutting,
                "total_seconds": job.timing_total,
            },
        })

    return result


@router.get("/jobs")
def list_jobs(user: User = Depends(get_optional_user), db: Session = Depends(get_db)):
    user = _resolve_user(db, user)
    jobs = job_queue.get_user_jobs(db, user.id)
    return {
        "jobs": [
            {
                "id": j.id, "status": j.status, "filename": j.filename,
                "source": j.source, "language": j.target_language or "en",
                "aspect_ratio": j.aspect_ratio or "vertical_9_16",
                "error": j.error or None,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    }
