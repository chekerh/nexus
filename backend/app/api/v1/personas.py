"""Persona API — CRUD + content generation from transcript."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...core.model_router import get_ollama_model_for_task
from ...models.persona import Persona, Schedule
from ...models.user import User
from ..deps import get_current_user

logger = logging.getLogger("nexus.personas")

router = APIRouter(tags=["personas"])


class PersonaCreate(BaseModel):
    name: str
    bio: str = ""
    voice_description: str = ""
    target_audience: str = ""
    content_pillars: str = "[]"
    tone: str = "professional"
    brand_colors: str = '{"primary":"#00e5ff","secondary":"#8b5cf6"}'
    auto_approve: bool = False


class PersonaUpdate(BaseModel):
    name: str | None = None
    bio: str | None = None
    voice_description: str | None = None
    target_audience: str | None = None
    content_pillars: str | None = None
    tone: str | None = None
    brand_colors: str | None = None
    auto_approve: bool | None = None
    is_active: bool | None = None


@router.get("/personas")
def list_personas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    personas = db.query(Persona).filter(Persona.user_id == user.id).order_by(Persona.created_at.desc()).limit(200).all()
    return {"personas": [_p_dict(p) for p in personas]}


@router.post("/personas")
def create_persona(payload: PersonaCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    persona = Persona(
        user_id=user.id,
        name=payload.name,
        bio=payload.bio,
        voice_description=payload.voice_description,
        target_audience=payload.target_audience,
        content_pillars=payload.content_pillars,
        tone=payload.tone,
        brand_colors=payload.brand_colors,
        auto_approve=payload.auto_approve,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return {"persona": _p_dict(persona)}


@router.get("/personas/{persona_id}")
def get_persona(persona_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))
    return {"persona": _p_dict(persona)}


@router.put("/personas/{persona_id}")
def update_persona(
    persona_id: str, payload: PersonaUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))
    for field in payload.model_dump(exclude_unset=True):
        setattr(persona, field, getattr(payload, field))
    db.commit()
    db.refresh(persona)
    return {"persona": _p_dict(persona)}


@router.delete("/personas/{persona_id}")
def delete_persona(persona_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))
    db.delete(persona)
    db.commit()
    return {"ok": True}


# --- Content Generation ---


class RepurposeRequest(BaseModel):
    transcript: str
    platforms: list[str] = ["twitter", "linkedin", "instagram", "facebook"]
    count_per_platform: int = 1


@router.post("/personas/{persona_id}/repurpose")
def repurpose_content(
    persona_id: str, payload: RepurposeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))

    results = {}
    for platform in payload.platforms:
        posts = _generate_platform_posts(persona, payload.transcript, platform, payload.count_per_platform)
        results[platform] = posts

    return {"results": results}


def _generate_platform_posts(persona: Persona, transcript: str, platform: str, count: int) -> list[dict]:
    """Use Ollama to generate platform-specific posts from transcript + persona voice."""
    platform_guides = {
        "twitter": "X/Twitter posts (max 280 chars each, thread-style, punchy hooks)",
        "linkedin": "LinkedIn posts (professional tone, 2-3 paragraphs, value-first, use line breaks)",
        "instagram": "Instagram captions (storytelling, 3-5 lines, emojis, CTA at end, hashtags)",
        "facebook": "Facebook posts (conversational, 3-4 paragraphs, question to engage comments)",
        "tiktok": "TikTok captions (short, punchy, 1-2 lines, trending format, hashtags)",
        "youtube": "YouTube descriptions (SEO-optimized, 2-3 paragraphs, timestamps, links, CTA)",
    }

    guide = platform_guides.get(platform, f"{platform} posts")
    pillars = json.loads(persona.content_pillars or "[]")
    pillars_text = ", ".join(pillars[:3]) if pillars else "general content"

    system = (
        f"You are a social media content strategist writing for {platform}. "
        f"Brand voice: {persona.voice_description or persona.name}. "
        f"Tone: {persona.tone}. Target audience: {persona.target_audience or 'general'}. "
        f"Content pillars: {pillars_text}. "
        f"Write {count} {'thread' if platform == 'twitter' else 'post'} "
        f"that feel authentic to this brand. "
        f"Guidelines for {platform}: {guide}. "
        f'Return STRICT JSON array: [{{"title": "...", "body": "..."}}]'
    )

    try:
        import ollama

        model = get_ollama_model_for_task("caption_style")
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Video transcript:\n\n{transcript[:3000]}\n\nGenerate {count} {platform} posts.",
                },
            ],
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={"temperature": 0.4, "num_predict": 1024},
        )
        content = (response.get("message", {}) or {}).get("content", "").strip()
        import re

        match = re.search(r"\[[\s\S]*\]", content)
        if match:
            posts = json.loads(match.group(0))
            if isinstance(posts, list):
                return posts[:count]
    except Exception as e:
        logger.warning("Ollama content generation failed for %s: %s", platform, e)

    return [{"title": f"{platform} post", "body": transcript[:200]}]


# --- Schedules ---


class ScheduleCreate(BaseModel):
    platform: str
    day_of_week: int = -1
    time: str = "09:00"


@router.get("/personas/{persona_id}/schedules")
def list_schedules(persona_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))
    schedules = db.query(Schedule).filter(Schedule.persona_id == persona_id).limit(200).all()
    return {"schedules": [_s_dict(s) for s in schedules]}


@router.post("/personas/{persona_id}/schedules")
def create_schedule(
    persona_id: str, payload: ScheduleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))
    schedule = Schedule(
        persona_id=persona_id,
        platform=payload.platform,
        day_of_week=payload.day_of_week,
        time=payload.time,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return {"schedule": _s_dict(schedule)}


@router.delete("/personas/{persona_id}/schedules/{schedule_id}")
def delete_schedule(
    persona_id: str, schedule_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.persona_id == persona_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail=_("error.schedule-not-found"))
    persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
    if not persona:
        raise HTTPException(status_code=404, detail=_("error.persona-not-found"))
    db.delete(sched)
    db.commit()
    return {"ok": True}


def _p_dict(p: Persona) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "bio": p.bio,
        "voice_description": p.voice_description,
        "target_audience": p.target_audience,
        "content_pillars": json.loads(p.content_pillars) if p.content_pillars else [],
        "tone": p.tone,
        "brand_colors": json.loads(p.brand_colors) if p.brand_colors else {},
        "auto_approve": p.auto_approve,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _s_dict(s: Schedule) -> dict:
    return {
        "id": s.id,
        "persona_id": s.persona_id,
        "platform": s.platform,
        "day_of_week": s.day_of_week,
        "time": s.time,
        "is_active": s.is_active,
    }
