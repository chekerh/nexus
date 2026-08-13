"""Dunning — automatic payment retry and downgrade logic."""

import logging
from datetime import UTC, datetime, timedelta

from ..core.database import SessionLocal
from ..models.user import SubscriptionTier, User
from .email import send_dunning_notice

logger = logging.getLogger("nexus.dunning")

DUNNING_MAX_ATTEMPTS = 3
DUNNING_COOLDOWN_HOURS = 24


def handle_failed_payment(stripe_customer_id: str) -> None:
    """Increment dunning counter and notify user. Downgrade after max attempts."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.stripe_customer_id == stripe_customer_id).first()
        if not user:
            logger.warning("Dunning: no user found for customer %s", stripe_customer_id)
            return

        user.dunning_count = (user.dunning_count or 0) + 1
        user.last_dunning_at = datetime.now(UTC)
        db.commit()

        send_dunning_notice(user.email, user.dunning_count, DUNNING_MAX_ATTEMPTS)

        if user.dunning_count >= DUNNING_MAX_ATTEMPTS:
            _downgrade_to_free(user, db)
    finally:
        db.close()


def _downgrade_to_free(user: User, db) -> None:
    """Downgrade user to FREE tier and clear dunning counter."""
    user.subscription_tier = SubscriptionTier.FREE
    user.credits_limit_month = 5
    user.stripe_subscription_id = ""
    user.dunning_count = 0
    db.commit()
    logger.info("Dunning: downgraded user %s to FREE after max attempts", user.id)


def process_dunning_queue() -> None:
    """Periodic task: process users who are past dunning cooldown."""
    db = SessionLocal()
    try:
        deadline = datetime.now(UTC) - timedelta(hours=DUNNING_COOLDOWN_HOURS)
        stale = (
            db.query(User)
            .filter(
                User.dunning_count > 0,
                User.dunning_count < DUNNING_MAX_ATTEMPTS,
                User.last_dunning_at < deadline,
                User.subscription_tier != SubscriptionTier.FREE,
            )
            .all()
        )
        for user in stale:
            logger.info("Dunning queue: notifying user %s (attempt %d)", user.id, user.dunning_count)
            send_dunning_notice(user.email, user.dunning_count, DUNNING_MAX_ATTEMPTS)
    finally:
        db.close()
