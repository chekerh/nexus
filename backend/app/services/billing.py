"""Stripe billing integration for subscription management.

In production, set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in .env.
In local/dev mode, billing operations log instead of calling Stripe API.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from ..models.user import User, SubscriptionTier
from ..core.config import settings

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

HAS_STRIPE = False
if STRIPE_SECRET_KEY:
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        HAS_STRIPE = True
    except ImportError:
        logger.warning("stripe package not installed")


PRICING = {
    SubscriptionTier.FREE: {"price": 0, "label": "Free", "credits": 5},
    SubscriptionTier.PRO: {"price": 29, "label": "Pro", "credits": 50, "stripe_price_id": os.getenv("STRIPE_PRO_PRICE_ID", "")},
    SubscriptionTier.ENTERPRISE: {"price": 99, "label": "Enterprise", "credits": 500, "stripe_price_id": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "")},
}


def create_checkout_session(user: User, tier: SubscriptionTier) -> dict:
    """Create a Stripe checkout session for the given tier."""
    if tier == SubscriptionTier.FREE:
        return {"url": None, "message": "Free tier - no payment needed"}

    if not HAS_STRIPE:
        return _mock_checkout(user, tier)

    price_id = PRICING[tier].get("stripe_price_id", "")
    if not price_id:
        return {"error": f"No price configured for {tier.value}"}

    import stripe
    try:
        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id or None,
            customer_email=user.email if not user.stripe_customer_id else None,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=settings.PUBLIC_BASE_URL + "/settings?billing=success",
            cancel_url=settings.PUBLIC_BASE_URL + "/settings?billing=cancel",
            metadata={"user_id": user.id, "tier": tier.value},
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Stripe checkout failed: {e}")
        return {"error": str(e)}


def _mock_checkout(user: User, tier: SubscriptionTier) -> dict:
    """Local dev mock - logs instead of charging."""
    logger.info(f"[MOCK] Checkout for user {user.id}: {tier.value}")
    return {"url": "/settings?billing=success&mock=true", "session_id": "mock_ses_" + user.id}


def handle_subscription_updated(payload: dict) -> bool:
    """Handle Stripe subscription update webhook."""
    try:
        customer_id = payload.get("customer", "")
        status = payload.get("status", "")
        items = payload.get("items", {}).get("data", [])
        if not items:
            return False
        price_id = items[0].get("price", {}).get("id", "")
        tier = SubscriptionTier.FREE
        for t, info in PRICING.items():
            if info.get("stripe_price_id") == price_id:
                tier = t
                break

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if user:
                user.subscription_tier = tier
                user.stripe_subscription_id = payload.get("id", "")
                db.commit()
        finally:
            db.close()
        return True
    except Exception as e:
        logger.error(f"Webhook handling failed: {e}")
        return False


def get_pricing_info() -> dict:
    return {tier.value: info for tier, info in PRICING.items()}


from ..core.database import SessionLocal
