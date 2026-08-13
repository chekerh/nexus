"""Admin dashboard API — stats, health, analytics, user management, self-improvement."""

import contextlib
import logging
import os
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import SessionLocal, get_db
from ...core.i18n import _
from ...models.account import SocialAccount
from ...models.campaign import Campaign
from ...models.feature_suggestion import FeatureSuggestion, SuggestionCategory, SuggestionEffort, SuggestionStatus
from ...models.job import Job
from ...models.persona import Persona, Post
from ...models.publish_history import PublishHistory
from ...models.template import Template
from ...models.user import User
from ...models.whop import WhopLicense
from ..deps import get_current_user

logger = logging.getLogger("nexus.admin")
router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=403, detail=_("error.account-disabled"))
    if not user.is_admin:
        raise HTTPException(status_code=403, detail=_("error.admin-access-required"))
    return user


@router.get("/stats")
def admin_stats(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Dashboard overview statistics."""
    total_users = db.query(User).count()
    total_personas = db.query(Persona).count()
    total_posts = db.query(Post).count()
    total_campaigns = db.query(Campaign).count()
    total_accounts = db.query(SocialAccount).count()
    total_templates = db.query(Template).count()
    total_scheduled_posts = db.query(Post).filter(Post.scheduled_at.isnot(None), Post.status != "posted").count()

    posted = db.query(Post).filter(Post.status == "posted").count()
    scheduled = db.query(Post).filter(Post.status == "scheduled").count()
    failed = db.query(Post).filter(Post.status == "failed").count()
    pending = db.query(Post).filter(Post.status == "pending").count()
    drafts = db.query(Post).filter(Post.status == "draft").count()

    platform_counts = {}
    for p in db.query(Post.platform, sa_func.count(Post.platform)).group_by(Post.platform).all():
        platform_counts[p[0]] = p[1]

    tier_counts = {"free": 0, "pro": 0, "enterprise": 0}
    for t, cnt in (
        db.query(User.subscription_tier, sa_func.count(User.subscription_tier)).group_by(User.subscription_tier).all()
    ):
        key = t.value if hasattr(t, "value") else str(t)
        tier_counts[key] = cnt

    pub_success_log = db.query(PublishHistory).filter(PublishHistory.status == "success").count()
    pub_failed_log = db.query(PublishHistory).filter(PublishHistory.status == "failed").count()

    pro_licenses = db.query(WhopLicense).filter(WhopLicense.tier == "pro", WhopLicense.status == "active").count()
    enterprise_licenses = (
        db.query(WhopLicense).filter(WhopLicense.tier == "enterprise", WhopLicense.status == "active").count()
    )

    return {
        "total_users": total_users,
        "total_personas": total_personas,
        "total_posts": total_posts,
        "total_campaigns": total_campaigns,
        "total_accounts": total_accounts,
        "total_templates": total_templates,
        "total_scheduled_posts": total_scheduled_posts,
        "publish_success": posted,
        "publish_failed": failed,
        "publish_scheduled": scheduled,
        "publish_pending": pending,
        "publish_drafts": drafts,
        "platforms": platform_counts,
        "tiers": tier_counts,
        "publish_history_total": pub_success_log + pub_failed_log,
        "publish_history_success": pub_success_log,
        "publish_history_failed": pub_failed_log,
        "pro_licenses": pro_licenses,
        "enterprise_licenses": enterprise_licenses,
    }


@router.get("/health")
def admin_health(user: User = Depends(_require_admin)):
    """System health — probe key services."""
    results: dict[str, object] = {}

    try:
        import time

        from sqlalchemy import text as sa_text

        db = SessionLocal()
        t0 = time.time()
        db.execute(sa_text("SELECT 1"))
        latency = int((time.time() - t0) * 1000)
        db.close()
        results["database"] = {"status": "ok", "latency_ms": latency}
    except Exception as e:
        results["database"] = {"status": "error", "message": str(e)}

    try:
        db2 = SessionLocal()
        pending = db2.query(Job).filter(Job.status == "pending").count()
        running = db2.query(Job).filter(Job.status == "running").count()
        db2.close()
        results["job_queue"] = {"status": "ok", "pending_jobs": pending, "running_jobs": running}
    except Exception as e:
        results["job_queue"] = {"status": "error", "message": str(e)}

    try:
        from ...core.publisher import PublishHistoryStore

        PublishHistoryStore()
        results["publish_worker"] = {"status": "ok", "store_ready": True}
    except Exception as e:
        results["publish_worker"] = {"status": "error", "message": str(e)}

    try:
        from ...services.scheduler import post_scheduler

        results["scheduler"] = {
            "status": "ok" if post_scheduler._running else "error",
            "running": post_scheduler._running,
        }
    except Exception as e:
        results["scheduler"] = {"status": "error", "message": str(e)}

    config_checks = {
        "ollama_model": bool(settings.OLLAMA_MODEL),
        "public_base_url": bool(settings.PUBLIC_BASE_URL),
        "youtube_configured": bool(settings.YOUTUBE_CLIENT_ID and settings.YOUTUBE_CLIENT_SECRET),
        "tiktok_configured": bool(settings.TIKTOK_CLIENT_KEY and settings.TIKTOK_CLIENT_SECRET),
        "whop_configured": bool(settings.WHOP_API_KEY),
        "stripe_configured": bool(settings.STRIPE_SECRET_KEY),
    }
    results["config"] = config_checks

    return results


@router.get("/publishing")
def admin_publishing(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Publishing analytics per platform."""
    platform_stats = {}
    for p in ["youtube", "tiktok", "instagram", "facebook", "twitter", "linkedin"]:
        posts = db.query(Post).filter(Post.platform == p).limit(500).all()
        history_count = db.query(PublishHistory).filter(PublishHistory.platform == p).count()

        posted = sum(1 for post in posts if post.status == "posted")
        failed = sum(1 for post in posts if post.status == "failed")
        scheduled = sum(1 for post in posts if post.status == "scheduled")
        total = len(posts)

        platform_stats[p] = {
            "total": total,
            "posted": posted,
            "failed": failed,
            "scheduled": scheduled,
            "history_count": history_count,
        }

    total_history = db.query(PublishHistory).count()
    return {"platforms": platform_stats, "history_count": total_history}


@router.get("/users")
def admin_users(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """List all users with their details."""
    from sqlalchemy import case as sa_case
    from sqlalchemy import func as sa_func

    post_stats = (
        db.query(
            Post.user_id,
            sa_func.count(Post.id).label("total_posts"),
            sa_func.count(sa_case((Post.status == "posted", 1), else_=None)).label("published"),
            sa_func.count(sa_case((Post.status == "failed", 1), else_=None)).label("failed_publishes"),
            sa_func.count(sa_case((Post.title.ilike("%brain%"), 1), else_=None)).label("brainrot_posts"),
            sa_func.max(Post.created_at).label("last_post_at"),
        )
        .group_by(Post.user_id)
        .subquery()
    )
    persona_counts = (
        db.query(
            Persona.user_id,
            sa_func.count(Persona.id).label("cnt"),
        )
        .group_by(Persona.user_id)
        .subquery()
    )

    limit = min(int(db.query(Post).count() or 100), 200)
    users = (
        db.query(User, post_stats, persona_counts)
        .outerjoin(post_stats, User.id == post_stats.c.user_id)
        .outerjoin(persona_counts, User.id == persona_counts.c.user_id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name or u.email,
                "tier": u.subscription_tier.value
                if hasattr(u.subscription_tier, "value")
                else str(u.subscription_tier),
                "credits_used": u.credits_used_month,
                "credits_limit": u.credits_limit_month,
                "is_active": u.is_active,
                "personas": p_cnt.cnt if p_cnt else 0,
                "posts": ps.total_posts if ps else 0,
                "brainrot_posts": ps.brainrot_posts if ps else 0,
                "published": ps.published if ps else 0,
                "failed_publishes": ps.failed_publishes if ps else 0,
                "last_post_at": ps.last_post_at.isoformat() if ps and ps.last_post_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u, ps, p_cnt in users
        ]
    }


@router.get("/user-activity")
def admin_user_activity(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Recent activity across all users."""
    activities = []

    recent_posts = (
        db.query(Post, User).join(User, Post.user_id == User.id).order_by(Post.created_at.desc()).limit(50).all()
    )
    for post, puser in recent_posts:
        activities.append(
            {
                "type": "post",
                "user_id": puser.id,
                "user_email": puser.email,
                "user_name": puser.display_name or puser.email,
                "detail": f"{post.platform} — {post.title or 'untitled'}",
                "status": post.status,
                "media_path": post.media_path,
                "created_at": post.created_at.isoformat() if post.created_at else None,
            }
        )

    recent_jobs = db.query(Job, User).join(User, Job.user_id == User.id).order_by(Job.created_at.desc()).limit(50).all()
    for job, juser in recent_jobs:
        activities.append(
            {
                "type": "pipeline",
                "user_id": juser.id,
                "user_email": juser.email,
                "user_name": juser.display_name or juser.email,
                "detail": f"{job.filename or 'unknown'} — {job.status}",
                "status": job.status,
                "media_path": job.video_path or "",
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
        )

    activities.sort(key=lambda a: a.get("created_at", "") or "", reverse=True)
    return {"activities": activities[:100]}


class UserUpdateRequest(BaseModel):
    is_active: bool | None = None
    credits_limit: int | None = None


@router.put("/users/{user_id}")
def admin_update_user(
    user_id: str,
    payload: UserUpdateRequest,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Update a user — toggle active status, set credit limit."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=_("error.user-not-found"))

    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.credits_limit is not None:
        target.credits_limit_month = max(1, min(99999, payload.credits_limit))

    db.commit()
    return {"ok": True, "is_active": target.is_active, "credits_limit": target.credits_limit_month}


class InviteKeyCreateRequest(BaseModel):
    count: int = 1
    max_uses: int = 1
    expires_in_hours: int | None = 48


@router.get("/invite-keys")
def admin_list_invite_keys(
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from ...models.invite_key import InviteKey

    keys = db.query(InviteKey).order_by(InviteKey.created_at.desc()).limit(200).all()
    return {
        "invite_keys": [
            {
                "id": k.id,
                "code": k.code,
                "created_by": k.created_by,
                "max_uses": k.max_uses,
                "used_count": k.used_count,
                "is_active": k.is_active,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in keys
        ]
    }


@router.post("/invite-keys")
def admin_create_invite_keys(
    payload: InviteKeyCreateRequest,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    import secrets

    from ...models.invite_key import InviteKey

    keys = []
    count = max(1, min(100, payload.count))
    for _i in range(count):
        code = "nex-" + secrets.token_hex(8)
        expires_at = None
        if payload.expires_in_hours:
            expires_at = datetime.now(UTC) + timedelta(hours=payload.expires_in_hours)
        key = InviteKey(
            code=code,
            created_by=user.email,
            max_uses=payload.max_uses,
            expires_at=expires_at,
        )
        db.add(key)
        keys.append(code)
    db.commit()
    return {"created": len(keys), "invite_keys": keys}


@router.delete("/invite-keys/{key_id}")
def admin_revoke_invite_key(
    key_id: str,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    from ...models.invite_key import InviteKey

    key = db.query(InviteKey).filter(InviteKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail=_("error.invite-key-not-found"))
    key.is_active = False
    db.commit()
    return {"status": "revoked"}


@router.get("/accounts")
def admin_accounts(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """List all connected social accounts."""
    accounts = db.query(SocialAccount).order_by(SocialAccount.platform).limit(500).all()
    user_ids = {a.user_id for a in accounts if a.user_id}
    users_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return {
        "accounts": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "user_email": users_map[a.user_id].email if a.user_id in users_map else None,
                "platform": a.platform,
                "handle": a.account_name,
                "is_active": a.is_active,
                "has_tokens": bool(
                    a.oauth_refresh_token_enc or a.instagram_access_token_enc or a.tiktok_access_token_enc
                ),
                "token_expires_at": None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in accounts
        ]
    }


@router.get("/licenses")
def admin_licenses(user: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """List all Whop licenses."""
    licenses = db.query(WhopLicense).order_by(WhopLicense.created_at.desc()).limit(500).all()
    return {
        "licenses": [
            {
                "id": lic.id,
                "user_id": lic.user_id,
                "license_key": lic.license_key,
                "product_id": lic.product_id,
                "tier": lic.tier,
                "status": lic.status,
                "created_at": lic.created_at.isoformat() if lic.created_at else None,
            }
            for lic in licenses
        ]
    }


# ── Self-Improvement: Ollama-Powered Feature Brainstorm ──

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = settings.OLLAMA_MODEL or "qwen2.5:latest"

SYSTEM_PROMPT = """You are Nexus-UGC's self-improvement engine. Analyze the project structure and propose features, optimizations, and fixes.

For each suggestion, output exactly one valid JSON object per line (newline-delimited JSON) with these fields:
- "title": short feature name
- "category": one of "feature", "ui", "bugfix", "optimization", "security"
- "description": 1-2 sentence explanation
- "effort": "low", "medium", or "high"
- "files": array of likely file paths to modify

Output 3-5 suggestions. Only output the JSON lines, nothing else."""


# ── Feature Suggestions Persistence ──


class FeatureSuggestionCreate(BaseModel):
    title: str
    category: str
    description: str
    effort: str = "medium"
    files: list[str] = []
    source: str = "manual"


class FeatureSuggestionUpdate(BaseModel):
    status: str | None = None
    votes: int | None = None


@router.get("/feature-suggestions")
def admin_list_feature_suggestions(
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """List feature suggestions with filtering."""
    query = db.query(FeatureSuggestion).order_by(FeatureSuggestion.created_at.desc())

    if status:
        with contextlib.suppress(ValueError):
            query = query.filter(FeatureSuggestion.status == SuggestionStatus(status))
    if category:
        with contextlib.suppress(ValueError):
            query = query.filter(FeatureSuggestion.category == SuggestionCategory(category))

    total = query.count()
    suggestions = query.offset(offset).limit(limit).all()

    return {
        "suggestions": [s.to_dict() for s in suggestions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/feature-suggestions")
def admin_create_feature_suggestion(
    payload: FeatureSuggestionCreate,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Create a manual feature suggestion."""
    try:
        cat = SuggestionCategory(payload.category)
    except ValueError:
        cat = SuggestionCategory.FEATURE

    try:
        eff = SuggestionEffort(payload.effort)
    except ValueError:
        eff = SuggestionEffort.MEDIUM

    import json

    suggestion = FeatureSuggestion(
        title=payload.title[:500],
        category=cat,
        description=payload.description,
        effort=eff,
        files=json.dumps(payload.files),
        source=payload.source,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion.to_dict()


@router.put("/feature-suggestions/{suggestion_id}")
def admin_update_feature_suggestion(
    suggestion_id: str,
    payload: FeatureSuggestionUpdate,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Update a feature suggestion (status, votes)."""
    suggestion = db.query(FeatureSuggestion).filter(FeatureSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail=_("error.suggestion-not-found"))

    if payload.status is not None:
        try:
            new_status = SuggestionStatus(payload.status)
            suggestion.status = new_status
            if new_status == SuggestionStatus.IMPLEMENTED:
                suggestion.implemented_at = datetime.now(UTC)
            elif new_status == SuggestionStatus.IN_REVIEW:
                suggestion.reviewed_at = datetime.now(UTC)
        except ValueError:
            raise HTTPException(status_code=400, detail=_("error.invalid-suggestion-status")) from None

    if payload.votes is not None:
        suggestion.votes = max(0, payload.votes)

    suggestion.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(suggestion)
    return suggestion.to_dict()


class VoteRequest(BaseModel):
    direction: int = 1  # 1 for upvote, -1 for downvote


@router.post("/feature-suggestions/{suggestion_id}/vote")
def admin_vote_feature_suggestion(
    suggestion_id: str,
    payload: VoteRequest,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Vote on a feature suggestion."""
    suggestion = db.query(FeatureSuggestion).filter(FeatureSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail=_("error.suggestion-not-found"))

    # direction > 0 = upvote, direction < 0 = downvote
    vote_change = 1 if payload.direction > 0 else -1
    suggestion.votes = max(0, suggestion.votes + vote_change)
    suggestion.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(suggestion)
    return {"votes": suggestion.votes}


@router.delete("/feature-suggestions/{suggestion_id}")
def admin_delete_feature_suggestion(
    suggestion_id: str,
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Delete a feature suggestion."""
    suggestion = db.query(FeatureSuggestion).filter(FeatureSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail=_("error.suggestion-not-found"))

    db.delete(suggestion)
    db.commit()
    return {"status": "deleted"}


# Update suggest-features to persist suggestions
@router.post("/suggest-features")
async def admin_suggest_features(
    user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Scan the codebase and use Ollama to suggest improvements. Persists results."""
    backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "backend")
    frontend_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "frontend"
    )

    def collect_files(directory, max_files=15, max_lines=300):
        collected = []
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__pycache__", "node_modules", "venv", ".git"))]
            for f in files:
                if not (f.endswith(".py") or f.endswith(".js") or f.endswith(".html")):
                    continue
                fpath = os.path.join(root, f)
                rel = os.path.relpath(fpath, os.path.join(directory, ".."))
                try:
                    with open(fpath, errors="ignore") as fh:
                        lines = fh.readlines()
                    collected.append(f"{'=' * 60}\nFILE: {rel}\n{'=' * 60}\n" + "".join(lines[:max_lines]))
                    if len(lines) > max_lines:
                        collected.append(f"... ({len(lines) - max_lines} more lines omitted)\n")
                except Exception:
                    continue
                if len(collected) >= max_files:
                    break
            if len(collected) >= max_files:
                break
        return collected

    backend_src = collect_files(backend_dir, max_files=12, max_lines=200)
    frontend_src = collect_files(frontend_dir, max_files=8, max_lines=150)

    context = "# Nexus-UGC Codebase Analysis\n\n" + "\n".join(backend_src) + "\n\n" + "\n".join(frontend_src)

    prompt = SYSTEM_PROMPT + "\n\n" + context[:12000]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
    except httpx.ConnectError:
        return {"suggestions": [], "error": f"Could not connect to Ollama at {OLLAMA_URL}. Is it running?"}
    except Exception as e:
        return {"suggestions": [], "error": f"Ollama error: {str(e)}"}

    suggestions = []
    import json

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            suggestions.append(item)
        except json.JSONDecodeError:
            continue

    # Persist new suggestions
    persisted = []
    for item in suggestions:
        # Check if similar suggestion exists (by title)
        existing = db.query(FeatureSuggestion).filter(FeatureSuggestion.title == item.get("title", "")).first()

        if existing:
            # Update existing
            existing.description = item.get("description", existing.description)
            existing.updated_at = datetime.now(UTC)
            persisted.append(existing.to_dict())
        else:
            try:
                cat = SuggestionCategory(item.get("category", "feature"))
            except ValueError:
                cat = SuggestionCategory.FEATURE
            try:
                eff = SuggestionEffort(item.get("effort", "medium"))
            except ValueError:
                eff = SuggestionEffort.MEDIUM

            new_suggestion = FeatureSuggestion(
                title=item.get("title", "Untitled")[:500],
                category=cat,
                description=item.get("description", ""),
                effort=eff,
                files=json.dumps(item.get("files", [])),
                source="ollama",
                ollama_model=OLLAMA_MODEL,
            )
            db.add(new_suggestion)
            db.flush()
            persisted.append(new_suggestion.to_dict())

    db.commit()

    return {"suggestions": persisted, "model": OLLAMA_MODEL, "count": len(persisted)}
