"""Stripe billing integration for subscription management.

In production, set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in .env.
In local/dev mode, billing operations log instead of calling Stripe API.
"""

import logging

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.user import SubscriptionTier, User

logger = logging.getLogger(__name__)

HAS_STRIPE = False
if settings.STRIPE_SECRET_KEY:
    try:
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        HAS_STRIPE = True
    except ImportError:
        logger.warning("stripe package not installed")


PRICING = {
    SubscriptionTier.FREE: {"price": 0, "label": "Free", "credits": 5},
    SubscriptionTier.PRO: {"price": 29, "label": "Pro", "credits": 50, "stripe_price_id": settings.STRIPE_PRO_PRICE_ID},
    SubscriptionTier.ENTERPRISE: {
        "price": 99,
        "label": "Enterprise",
        "credits": 500,
        "stripe_price_id": settings.STRIPE_ENTERPRISE_PRICE_ID,
    },
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
            success_url=settings.PUBLIC_BASE_URL + "/billing.html?checkout=success",
            cancel_url=settings.PUBLIC_BASE_URL + "/billing.html?checkout=cancel",
            metadata={"user_id": user.id, "tier": tier.value},
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Stripe checkout failed: {e}")
        return {"error": str(e)}


def _mock_checkout(user: User, tier: SubscriptionTier) -> dict:
    """Local dev mock - logs instead of charging."""
    logger.info(f"[MOCK] Checkout for user {user.id}: {tier.value}")
    return {"url": "/billing.html?checkout=success&mock=true", "session_id": "mock_ses_" + user.id}


def create_portal_session(user: User) -> dict:
    """Create a Stripe customer portal session for managing subscriptions."""
    if not HAS_STRIPE:
        return {"url": "/billing.html?portal=mock", "message": "Dev mode - no portal needed"}

    if not user.stripe_customer_id:
        return {"error": "No Stripe customer record found"}

    import stripe

    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=settings.PUBLIC_BASE_URL + "/billing.html",
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"Stripe portal session failed: {e}")
        return {"error": str(e)}


def cancel_subscription(user: User) -> dict:
    """Cancel the user's active Stripe subscription at period end."""
    if not HAS_STRIPE:
        logger.info(f"[MOCK] Cancel subscription for user {user.id}")
        _update_user_tier(user.id, SubscriptionTier.FREE)
        return {"message": "Subscription cancelled (dev mode)", "tier": "free"}

    if not user.stripe_subscription_id:
        return {"error": "No active subscription found"}

    import stripe

    try:
        stripe.Subscription.modify(
            user.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        logger.info(f"Cancelled subscription {user.stripe_subscription_id} for user {user.id}")
        return {"message": "Subscription will cancel at period end", "cancel_at_period_end": True}
    except Exception as e:
        logger.error(f"Stripe cancel failed: {e}")
        return {"error": str(e)}


def _update_user_tier(user_id: str, tier: SubscriptionTier):
    """Update user subscription tier in DB."""

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.subscription_tier = tier
            db.commit()
    finally:
        db.close()


def handle_subscription_updated(payload: dict) -> bool:
    """Handle Stripe subscription update webhook."""
    try:
        customer_id = payload.get("customer", "")
        payload.get("status", "")
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
