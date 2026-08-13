"""Campaign API — CRUD, activate, pause, and auto-publish integration."""

import contextlib
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.i18n import _
from ...models.campaign import Campaign
from ...models.persona import Post
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    platforms: str = '["youtube","instagram","tiktok"]'
    persona_id: str = ""
    start_date: str | None = None
    end_date: str | None = None
    daily_post_count: str = ""


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    platforms: str | None = None
    persona_id: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    daily_post_count: str | None = None
    is_active: bool | None = None


@router.get("/campaigns")
def list_campaigns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaigns = (
        db.query(Campaign).filter(Campaign.user_id == user.id).order_by(Campaign.created_at.desc()).limit(200).all()
    )
    return {"campaigns": [_c_dict(c) for c in campaigns]}


@router.post("/campaigns")
def create_campaign(payload: CampaignCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    start = None
    if payload.start_date:
        with contextlib.suppress(Exception):
            start = datetime.fromisoformat(payload.start_date.replace("Z", "+00:00"))
    end = None
    if payload.end_date:
        with contextlib.suppress(Exception):
            end = datetime.fromisoformat(payload.end_date.replace("Z", "+00:00"))

    campaign = Campaign(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        platforms=payload.platforms,
        persona_id=payload.persona_id,
        start_date=start,
        end_date=end,
        daily_post_count=payload.daily_post_count or "",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return {"campaign": _c_dict(campaign)}


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=_("error.campaign-not-found"))

    # Get posts in this campaign
    posts = db.query(Post).filter(Post.campaign_id == campaign_id).order_by(Post.scheduled_at.asc()).limit(200).all()

    return {
        "campaign": _c_dict(campaign),
        "posts": [_post_summary(p) for p in posts],
    }


@router.put("/campaigns/{campaign_id}")
def update_campaign(
    campaign_id: str, payload: CampaignUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=_("error.campaign-not-found"))

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ("start_date", "end_date") and value:
            with contextlib.suppress(Exception):
                setattr(campaign, field, datetime.fromisoformat(value.replace("Z", "+00:00")))
        elif field not in ("start_date", "end_date"):
            setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return {"campaign": _c_dict(campaign)}


@router.post("/campaigns/{campaign_id}/activate")
def activate_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=_("error.campaign-not-found"))
    campaign.status = "active"
    campaign.is_active = True
    db.commit()
    return {"ok": True, "status": "active"}


@router.post("/campaigns/{campaign_id}/pause")
def pause_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=_("error.campaign-not-found"))
    campaign.status = "paused"
    campaign.is_active = False
    db.commit()
    return {"ok": True, "status": "paused"}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=_("error.campaign-not-found"))
    db.delete(campaign)
    db.commit()
    return {"ok": True}


def _c_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "platforms": json.loads(c.platforms) if c.platforms else [],
        "persona_id": c.persona_id,
        "status": c.status,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "daily_post_count": json.loads(c.daily_post_count) if c.daily_post_count else {},
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _post_summary(p: Post) -> dict:
    return {
        "id": p.id,
        "platform": p.platform,
        "title": p.title,
        "status": p.status,
        "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
    }
