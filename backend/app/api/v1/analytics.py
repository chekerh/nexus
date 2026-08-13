"""Dashboard analytics — account status, published content, and platform metrics."""

import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.i18n import _
from ...models.account import SocialAccount
from ...models.job import Job
from ...models.persona import Post
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(tags=["analytics"])


def _date_trunc_expr(column, interval: str):
    """Build a date-truncation SQL expression for the given column and interval.

    Uses SQLAlchemy function expressions instead of raw SQL strings to avoid
    SQL injection via f-string interpolation.
    """
    if interval == "day":
        return sa_func.date(column)
    elif interval == "week":
        return sa_func.date(column, "weekday 1", "-7 days")
    else:
        return sa_func.strftime("%Y-%m", column)


@router.get("/analytics/dashboard")
def get_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Aggregate dashboard data: account status + published content summary."""
    accounts = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == user.id,
            SocialAccount.is_active,
        )
        .all()
    )

    posts = (
        db.query(Post)
        .filter(
            Post.user_id == user.id,
        )
        .order_by(Post.created_at.desc())
        .limit(50)
        .all()
    )

    account_summary = []
    for acct in accounts:
        token_ok = False
        if acct.platform == "youtube":
            token_ok = bool(acct.oauth_refresh_token_enc)
        elif acct.platform == "instagram":
            token_ok = bool(acct.instagram_access_token_enc)
        elif acct.platform == "tiktok":
            token_ok = bool(acct.tiktok_access_token_enc)
        elif acct.platform == "twitter":
            token_ok = bool(acct.twitter_access_token_enc or acct.oauth_refresh_token_enc)
        elif acct.platform == "facebook":
            token_ok = bool(acct.facebook_access_token_enc)
        elif acct.platform == "linkedin":
            token_ok = bool(acct.linkedin_access_token_enc or acct.oauth_refresh_token_enc)

        account_summary.append(
            {
                "id": acct.id,
                "platform": acct.platform,
                "name": acct.account_name,
                "is_system": acct.account_name.startswith("System "),
                "token_ok": token_ok,
                "auth_mode": acct.auth_mode,
                "created_at": acct.created_at.isoformat() if acct.created_at else "",
            }
        )

    post_summary = []
    for p in posts:
        post_summary.append(
            {
                "id": p.id,
                "platform": p.platform,
                "status": p.status,
                "title": p.title or "",
                "error": p.error or "",
                "created_at": p.created_at.isoformat() if p.created_at else "",
                "posted_at": p.posted_at.isoformat() if p.posted_at else "",
                "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else "",
            }
        )

    status_counts: dict[str, int] = {}
    for p in posts:
        status_counts[p.status] = status_counts.get(p.status, 0) + 1

    platform_counts: dict[str, int] = {}
    for p in posts:
        platform_counts[p.platform] = platform_counts.get(p.platform, 0) + 1

    return {
        "accounts": account_summary,
        "total_accounts": len(account_summary),
        "connected_accounts": sum(1 for a in account_summary if a["token_ok"]),
        "disconnected_accounts": sum(1 for a in account_summary if not a["token_ok"]),
        "posts": post_summary,
        "total_posts": len(post_summary),
        "status_counts": status_counts,
        "platform_counts": platform_counts,
    }


@router.get("/analytics/timeseries")
def get_timeseries(
    metric: str = Query("posts", pattern="^(posts|jobs|users|publish_success|publish_failed)$"),
    interval: str = Query("day", pattern="^(day|week|month)$"),
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Time-series data for a given metric and interval."""
    now = datetime.now(UTC)
    start = now - timedelta(days=days)

    results = []
    if metric == "posts":
        query = db.query(_date_trunc_expr(Post.created_at, interval).label("date"), sa_func.count().label("count"))
        query = query.filter(Post.created_at >= start)
        if not user.is_admin:
            query = query.filter(Post.user_id == user.id)
        rows = query.group_by(_date_trunc_expr(Post.created_at, interval)).order_by("date").all()
        results = [{"date": str(r[0]), "count": r[1]} for r in rows]

    elif metric == "jobs":
        query = db.query(_date_trunc_expr(Job.created_at, interval).label("date"), sa_func.count().label("count"))
        query = query.filter(Job.created_at >= start)
        if not user.is_admin:
            query = query.filter(Job.user_id == user.id)
        rows = query.group_by(_date_trunc_expr(Job.created_at, interval)).order_by("date").all()
        results = [{"date": str(r[0]), "count": r[1]} for r in rows]

    elif metric == "users":
        if not user.is_admin:
            raise HTTPException(status_code=403, detail=_("error.admin-only"))
        rows = db.query(_date_trunc_expr(User.created_at, interval).label("date"), sa_func.count().label("count"))
        rows = rows.filter(User.created_at >= start)
        rows = rows.group_by(_date_trunc_expr(User.created_at, interval)).order_by("date").all()
        results = [{"date": str(r[0]), "count": r[1]} for r in rows]

    elif metric in ("publish_success", "publish_failed"):
        status = "posted" if metric == "publish_success" else "failed"
        query = db.query(_date_trunc_expr(Post.created_at, interval).label("date"), sa_func.count().label("count"))
        query = query.filter(Post.created_at >= start, Post.status == status)
        if not user.is_admin:
            query = query.filter(Post.user_id == user.id)
        rows = query.group_by(_date_trunc_expr(Post.created_at, interval)).order_by("date").all()
        results = [{"date": str(r[0]), "count": r[1]} for r in rows]

    return {"metric": metric, "interval": interval, "days": days, "data": results}


@router.get("/analytics/funnel")
def get_funnel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Conversion funnel: upload → transcribe → analyze → render → publish."""
    base = db.query(Job)
    if not user.is_admin:
        base = base.filter(Job.user_id == user.id)

    row = (
        base.with_entities(
            sa_func.count().label("total"),
            sa_func.sum(case((Job.transcript != "", 1), else_=0)).label("transcribed"),
            sa_func.sum(case((Job.analysis_json != "", 1), else_=0)).label("analyzed"),
            sa_func.sum(case((Job.clips_json != "", 1), else_=0)).label("rendered"),
            sa_func.sum(case((Job.status == "completed", 1), else_=0)).label("completed"),
        )
        .filter()
        .first()
    )

    total = row.total if row else 0
    transcribed = row.transcribed if row else 0
    analyzed = row.analyzed if row else 0
    rendered = row.rendered if row else 0
    completed = row.completed if row else 0

    published_query = db.query(sa_func.count()).select_from(Post).filter(Post.status == "posted")
    if not user.is_admin:
        published_query = published_query.filter(Post.user_id == user.id)
    published_count = published_query.scalar() or 0

    steps: list[dict[str, str | int | float]] = [
        {"stage": "upload", "count": total, "label": "Video Uploaded"},
        {"stage": "transcribe", "count": transcribed, "label": "Transcribed"},
        {"stage": "analyze", "count": analyzed, "label": "AI Analyzed"},
        {"stage": "render", "count": rendered, "label": "Clips Rendered"},
        {"stage": "completed", "count": completed, "label": "Completed"},
        {"stage": "publish", "count": published_count, "label": "Published"},
    ]

    for i, step in enumerate(steps):
        if i == 0:
            step["conversion"] = 100.0 if total > 0 else 0.0
        else:
            prev_count = int(steps[0]["count"])
            step["conversion"] = round((int(step["count"]) / prev_count * 100) if prev_count > 0 else 0, 1)

    return {"funnel": steps, "total_jobs": total}


@router.get("/analytics/revenue")
def get_revenue(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revenue metrics (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail=_("error.admin-access-required"))

    total_users = db.query(User).count()
    pro_users = db.query(User).filter(User.subscription_tier == "pro").count()
    enterprise_users = db.query(User).filter(User.subscription_tier == "enterprise").count()
    paid_users = pro_users + enterprise_users

    usage_total = db.query(sa_func.sum(User.credits_used_month)).scalar() or 0
    usage_avg = round(usage_total / max(1, total_users), 1)

    monthly_revenue = (pro_users * 29) + (enterprise_users * 99)

    active_30d = (
        db.query(Job).filter(Job.created_at >= datetime.now(UTC) - timedelta(days=30)).distinct(Job.user_id).count()
    )

    mrr = round(monthly_revenue, 2)
    arpu = round(monthly_revenue / max(1, total_users), 2)
    churned_30d = (
        db.query(User)
        .filter(
            User.is_active,
            User.id.notin_(
                db.query(Job.user_id).filter(Job.created_at >= datetime.now(UTC) - timedelta(days=30)).distinct()
            ),
        )
        .count()
        if active_30d > 0
        else 0
    )

    churn_rate = round(churned_30d / max(1, total_users) * 100, 1) if total_users > 0 else 0

    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "pro_users": pro_users,
        "enterprise_users": enterprise_users,
        "free_users": total_users - paid_users,
        "mrr": mrr,
        "arpu": arpu,
        "churn_rate_30d": churn_rate,
        "active_users_30d": active_30d,
        "total_usage_credits": usage_total,
        "avg_usage_credits": usage_avg,
    }


@router.get("/analytics/platforms")
def get_platforms(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-platform publishing performance comparison."""
    platforms_list = ["youtube", "tiktok", "instagram", "twitter", "facebook", "linkedin"]

    posts_query = db.query(
        Post.platform,
        sa_func.count().label("total"),
        sa_func.sum(case((Post.status == "posted", 1), else_=0)).label("posted"),
        sa_func.sum(case((Post.status == "failed", 1), else_=0)).label("failed"),
        sa_func.sum(case((Post.status == "scheduled", 1), else_=0)).label("scheduled"),
    )
    if not user.is_admin:
        posts_query = posts_query.filter(Post.user_id == user.id)
    rows = posts_query.group_by(Post.platform).all()

    result = {}
    for platform in platforms_list:
        match = next((r for r in rows if r.platform == platform), None)
        total = match.total if match else 0
        posted = match.posted if match else 0
        failed = match.failed if match else 0
        scheduled = match.scheduled if match else 0
        success_rate = round((posted / max(1, posted + failed)) * 100, 1) if (posted + failed) > 0 else None

        result[platform] = {
            "total": total,
            "posted": posted,
            "failed": failed,
            "scheduled": scheduled,
            "success_rate": success_rate,
        }

    return {"platforms": result}


def _csv_rows(scope: str, user: User, db: Session):
    """Generator that yields CSV rows one at a time for streaming export."""
    if scope == "posts":
        yield ["id", "platform", "status", "title", "created_at", "posted_at", "error"]
        posts_query = db.query(Post)
        if not user.is_admin:
            posts_query = posts_query.filter(Post.user_id == user.id)
        for p in posts_query.yield_per(200):
            yield [p.id, p.platform, p.status, p.title or "", p.created_at or "", p.posted_at or "", p.error or ""]

    elif scope == "jobs":
        yield ["id", "status", "filename", "source", "timing_total", "created_at", "completed_at"]
        jobs_query = db.query(Job)
        if not user.is_admin:
            jobs_query = jobs_query.filter(Job.user_id == user.id)
        for j in jobs_query.yield_per(200):
            yield [
                j.id,
                j.status,
                j.filename or "",
                j.source or "",
                j.timing_total or 0,
                j.created_at or "",
                j.completed_at or "",
            ]

    elif scope == "users" and user.is_admin:
        yield ["id", "email", "tier", "credits_used", "is_active", "created_at"]
        for u in db.query(User).yield_per(200):
            yield [
                u.id,
                u.email,
                u.subscription_tier.value if hasattr(u.subscription_tier, "value") else str(u.subscription_tier),
                u.credits_used_month,
                u.is_active,
                u.created_at or "",
            ]


def _csv_stream(scope: str, user: User, db: Session):
    """Stream CSV content row by row."""

    output = io.StringIO()
    writer = csv.writer(output)
    for row in _csv_rows(scope, user, db):
        writer.writerow(row)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


@router.get("/analytics/export/csv")
def export_csv(
    scope: str = Query("posts", pattern="^(posts|jobs|users)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export data as streaming CSV."""
    return StreamingResponse(
        _csv_stream(scope, user, db),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=nexus_{scope}_{datetime.now().strftime('%Y%m%d')}.csv"},
    )
