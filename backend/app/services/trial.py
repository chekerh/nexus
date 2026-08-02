"""Trial management — provisioning, expiry, reminders."""

import logging
from datetime import UTC, datetime, timedelta

from ..core.database import SessionLocal
from ..models.user import User

logger = logging.getLogger("nexus.trial")

TRIAL_DURATION_DAYS = 7
TRIAL_CREDITS = 10


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def provision_trial(user: User, days: int = TRIAL_DURATION_DAYS) -> None:
    """Set trial end date and provision trial credits."""
    user.trial_ends_at = datetime.now(UTC) + timedelta(days=days)
    user.credits_limit_month = TRIAL_CREDITS


def is_trial_active(user: User) -> bool:
    """Check if user is within trial period."""
    trial_ends_at = _ensure_utc(user.trial_ends_at)
    if not trial_ends_at:
        return False
    return datetime.now(UTC) < trial_ends_at


def is_trial_expired(user: User) -> bool:
    """Check if trial has expired."""
    trial_ends_at = _ensure_utc(user.trial_ends_at)
    if not trial_ends_at:
        return False
    return datetime.now(UTC) >= trial_ends_at


def expire_trials() -> list[str]:
    """Downgrade expired trial users to FREE and return their emails."""
    db = SessionLocal()
    expired = []
    try:
        users = (
            db.query(User)
            .filter(
                User.trial_ends_at.isnot(None),
                User.trial_ends_at < datetime.now(UTC),
            )
            .all()
        )
        for user in users:
            user.subscription_tier = "free"
            user.credits_limit_month = 5
            expired.append(user.email)
        db.commit()
        if expired:
            logger.info("Expired %d trials", len(expired))
    finally:
        db.close()
    return expired
