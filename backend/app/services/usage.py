"""Monthly usage quota tracking."""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.user import SubscriptionTier, User

logger = logging.getLogger(__name__)

TIER_LIMITS = {
    SubscriptionTier.FREE: {"credits": 5, "storage_mb": 512, "video_minutes": 30},
    SubscriptionTier.PRO: {"credits": 50, "storage_mb": 2048, "video_minutes": 120},
    SubscriptionTier.ENTERPRISE: {"credits": 500, "storage_mb": 4096, "video_minutes": 600},
}


def check_usage_quota(user: User) -> tuple[bool, str]:
    """Check if user has credits remaining. Returns (can_proceed, message)."""
    limits = TIER_LIMITS.get(user.subscription_tier, TIER_LIMITS[SubscriptionTier.FREE])
    if user.credits_used_month >= limits["credits"]:
        return False, f"Monthly credit limit reached ({limits['credits']}). Upgrade to continue."
    return True, ""


def increment_usage(user: User, db: Session):
    """Increment monthly credit usage by 1 using atomic SQL update."""
    db.execute(
        text("UPDATE users SET credits_used_month = COALESCE(credits_used_month, 0) + 1 WHERE id = :id"),
        {"id": user.id},
    )
    db.commit()
    db.refresh(user)
    limits = TIER_LIMITS.get(user.subscription_tier, TIER_LIMITS[SubscriptionTier.FREE])
    remaining = max(0, limits["credits"] - user.credits_used_month)
    logger.info("Credits used: %d/%d (%d remaining)", user.credits_used_month, limits["credits"], remaining)


def get_tier_limits(tier: SubscriptionTier | None) -> dict:
    """Get limits for a specific tier or defaults."""
    if tier is None:
        tier = SubscriptionTier.FREE
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
