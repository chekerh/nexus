"""Template API — CRUD for saved generator presets."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.i18n import _
from ...models.template import Template
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    niche: str = ""
    caption_style: str = "brain_rot"
    platform: str = "youtube"
    duration: str = "30"
    broll_mode: str = "none"
    language: str = "en"
    aspect_ratio: str = "vertical_9_16"
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    niche: str | None = None
    caption_style: str | None = None
    platform: str | None = None
    duration: str | None = None
    broll_mode: str | None = None
    language: str | None = None
    aspect_ratio: str | None = None
    is_default: bool | None = None


@router.get("/templates")
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    templates = (
        db.query(Template).filter(Template.user_id == user.id).order_by(Template.created_at.desc()).limit(200).all()
    )
    return {"templates": [_tpl_dict(t) for t in templates]}


@router.post("/templates")
def create_template(payload: TemplateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = Template(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        niche=payload.niche,
        caption_style=payload.caption_style,
        platform=payload.platform,
        duration=payload.duration,
        broll_mode=payload.broll_mode,
        language=payload.language,
        aspect_ratio=payload.aspect_ratio,
        is_default="true" if payload.is_default else "false",
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return {"template": _tpl_dict(tpl)}


@router.get("/templates/{template_id}")
def get_template(template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = db.query(Template).filter(Template.id == template_id, Template.user_id == user.id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail=_("error.template-not-found"))
    return {"template": _tpl_dict(tpl)}


@router.put("/templates/{template_id}")
def update_template(
    template_id: str, payload: TemplateUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    tpl = db.query(Template).filter(Template.id == template_id, Template.user_id == user.id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail=_("error.template-not-found"))
    for field in (
        "name",
        "description",
        "niche",
        "caption_style",
        "platform",
        "duration",
        "broll_mode",
        "language",
        "aspect_ratio",
    ):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(tpl, field, val)
    if payload.is_default is not None:
        tpl.is_default = "true" if payload.is_default else "false"
    tpl.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(tpl)
    return {"template": _tpl_dict(tpl)}


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = db.query(Template).filter(Template.id == template_id, Template.user_id == user.id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail=_("error.template-not-found"))
    db.delete(tpl)
    db.commit()
    return {"ok": True}


def _tpl_dict(t: Template) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "name": t.name,
        "description": t.description,
        "niche": t.niche,
        "caption_style": t.caption_style,
        "platform": t.platform,
        "duration": t.duration,
        "broll_mode": t.broll_mode,
        "language": t.language,
        "aspect_ratio": t.aspect_ratio,
        "is_default": t.is_default == "true",
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
