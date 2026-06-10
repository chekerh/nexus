"""Usage tracking and quota enforcement."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models.user import User, SubscriptionTier


TIER_LIMITS = {
    SubscriptionTier.FREE: {"credits_month": 5, "max_file_size_mb": 512, "max_video_minutes": 30},
    SubscriptionTier.PRO: {"credits_month": 50, "max_file_size_mb": 2048, "max_video_minutes": 120},
    SubscriptionTier.ENTERPRISE: {"credits_month": 500, "max_file_size_mb": 4096, "max_video_minutes": 600},
}


def check_usage_quota(db: Session, user: User) -> tuple[bool, str]:
    """Check if user has remaining credits this month."""
    limit = TIER_LIMITS.get(user.subscription_tier, TIER_LIMITS[SubscriptionTier.FREE])
    if user.credits_used_month >= limit["credits_month"]:
        return False, f"Monthly credit limit reached ({limit['credits_month']}). Upgrade for more."
    return True, ""


def increment_usage(db: Session, user: User):
    user.credits_used_month += 1
    db.commit()


def get_tier_limits(tier: SubscriptionTier) -> dict:
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
