"""Post Queue API — CRUD, status workflow, approval, scheduling."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.i18n import _
from ...models.persona import Persona, Post
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(tags=["posts"])


class PostCreate(BaseModel):
    persona_id: str
    platform: str
    content_type: str = "text"
    title: str = ""
    body: str = ""
    media_path: str = ""
    scheduled_at: str | None = None  # ISO datetime
    campaign_id: str = ""
    source_transcript: str = ""


class PostUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    scheduled_at: str | None = None
    media_path: str | None = None
    campaign_id: str | None = None


@router.get("/posts")
def list_posts(
    status: str | None = None,
    platform: str | None = None,
    persona_id: str | None = None,
    campaign_id: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Post).filter(Post.user_id == user.id)

    if status:
        query = query.filter(Post.status == status)
    if platform:
        query = query.filter(Post.platform == platform)
    if persona_id:
        query = query.filter(Post.persona_id == persona_id)
    if campaign_id:
        query = query.filter(Post.campaign_id == campaign_id)

    posts = (
        query.order_by(
            case((Post.scheduled_at.is_not(None), 0), else_=1),
            Post.scheduled_at.asc(),
            Post.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return {"posts": [_post_dict(p) for p in posts]}


@router.post("/posts")
def create_post(payload: PostCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == payload.persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))

    scheduled = None
    if payload.scheduled_at:
        try:
            scheduled = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=_("error.invalid-scheduled-at-format-create").format(scheduled_at=payload.scheduled_at),
            ) from None

    post = Post(
        persona_id=payload.persona_id,
        user_id=user.id,
        platform=payload.platform,
        content_type=payload.content_type,
        title=payload.title,
        body=payload.body,
        media_path=payload.media_path,
        scheduled_at=scheduled,
        campaign_id=payload.campaign_id,
        source_transcript=payload.source_transcript,
        status="draft",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"post": _post_dict(post)}


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail=_("error.post-not-found"))
    return {"post": _post_dict(post)}


@router.put("/posts/{post_id}")
def update_post(
    post_id: str, payload: PostUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail=_("error.post-not-found"))

    if payload.status:
        allowed = {"draft", "pending", "approved", "scheduled", "cancelled"}
        if payload.status not in allowed:
            raise HTTPException(
                status_code=400, detail=_("error.invalid-status").format(allowed=", ".join(sorted(allowed)))
            )
        post.status = payload.status

    if payload.title is not None:
        post.title = payload.title
    if payload.body is not None:
        post.body = payload.body
    if payload.media_path is not None:
        post.media_path = payload.media_path
    if payload.campaign_id is not None:
        post.campaign_id = payload.campaign_id
    if payload.scheduled_at is not None:
        if payload.scheduled_at == "":
            post.scheduled_at = None
        else:
            try:
                post.scheduled_at = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
            except Exception:
                raise HTTPException(status_code=400, detail=_("error.invalid-scheduled-at-format")) from None

    db.commit()
    db.refresh(post)
    return {"post": _post_dict(post)}


@router.post("/posts/{post_id}/approve")
def approve_post(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail=_("error.post-not-found"))
    if post.status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail=_("error.cannot-approve-post").format(status=post.status))

    post.status = "approved"
    post.scheduled_at = post.scheduled_at or datetime.now(UTC)
    db.commit()
    db.refresh(post)
    return {"post": _post_dict(post)}


class ScheduleRequest(BaseModel):
    scheduled_at: str


@router.post("/posts/{post_id}/schedule")
def schedule_post(
    post_id: str, payload: ScheduleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail=_("error.post-not-found"))

    try:
        dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail=_("error.invalid-iso-datetime")) from None

    post.scheduled_at = dt
    if post.status == "draft":
        post.status = "pending"
    elif post.status == "approved":
        post.status = "scheduled"
    db.commit()
    db.refresh(post)
    return {"post": _post_dict(post)}


@router.post("/posts/{post_id}/cancel")
def cancel_post(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail=_("error.post-not-found"))
    if post.status in ("posted", "cancelled"):
        raise HTTPException(status_code=400, detail=_("error.cannot-cancel-post").format(status=post.status))
    post.status = "cancelled"
    db.commit()
    return {"ok": True}


@router.delete("/posts/{post_id}")
def delete_post(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail=_("error.post-not-found"))
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.get("/calendar")
def get_calendar(
    start_date: str,
    end_date: str,
    persona_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all posts in a date range for calendar view."""
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail=_("error.invalid-date-format")) from None

    query = db.query(Post).filter(
        Post.user_id == user.id,
        Post.scheduled_at >= start,
        Post.scheduled_at <= end,
    )
    if persona_id:
        query = query.filter(Post.persona_id == persona_id)

    posts = query.order_by(Post.scheduled_at.asc()).all()
    return {"posts": [_post_dict(p) for p in posts]}


def _post_dict(p: Post) -> dict:
    return {
        "id": p.id,
        "persona_id": p.persona_id,
        "user_id": p.user_id,
        "job_id": p.job_id,
        "campaign_id": p.campaign_id,
        "platform": p.platform,
        "content_type": p.content_type,
        "title": p.title,
        "body": p.body,
        "media_path": p.media_path,
        "status": p.status,
        "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
        "posted_at": p.posted_at.isoformat() if p.posted_at else None,
        "error": p.error or None,
        "source_transcript": p.source_transcript,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
