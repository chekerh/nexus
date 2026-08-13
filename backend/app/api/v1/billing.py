"""Billing and subscription API."""

import logging
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...models.user import SubscriptionTier, User
from ...services.billing import (
    HAS_STRIPE,
    PRICING,
    cancel_subscription,
    create_checkout_session,
    create_portal_session,
    get_pricing_info,
    handle_subscription_updated,
)
from ...services.dunning import handle_failed_payment
from ...services.email import send_receipt
from ...services.trial import is_trial_active, provision_trial
from ..deps import get_current_user

router = APIRouter(tags=["billing"])


class CheckoutRequest(BaseModel):
    tier: str


@router.post("/billing/trial")
def start_trial(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start a trial for the current user."""
    if user.trial_ends_at:
        raise HTTPException(status_code=400, detail=_("error.trial-already-started"))
    provision_trial(user)
    db.add(user)
    db.commit()
    return {"trial_ends_at": user.trial_ends_at.isoformat(), "credits_limit": user.credits_limit_month}


@router.get("/billing/trial-status")
def trial_status(user: User = Depends(get_current_user)):
    """Check if user's trial is active."""
    return {
        "trial_active": is_trial_active(user),
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
    }


@router.get("/pricing")
def pricing():
    return get_pricing_info()


@router.post("/billing/checkout")
def checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
):
    try:
        tier = SubscriptionTier(payload.tier.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=_("error.invalid-tier")) from None

    result = create_checkout_session(user, tier)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/billing/portal")
def billing_portal(user: User = Depends(get_current_user)):
    """Create a Stripe customer portal session for managing the subscription."""
    result = create_portal_session(user)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/billing/cancel")
def billing_cancel(user: User = Depends(get_current_user)):
    """Cancel the active subscription at period end."""
    result = cancel_subscription(user)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="Stripe-Signature")):
    """Stripe webhook endpoint for subscription events.

    Verifies webhook signature to prevent forged events.
    Uses event.id for idempotency deduplication.
    """
    payload = await request.body()
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured — webhook endpoint disabled")
        raise HTTPException(status_code=500, detail=_("error.webhook-not-configured"))
    if not stripe_signature:
        raise HTTPException(status_code=400, detail=_("error.missing-stripe-signature"))

    db = next(get_db())
    try:
        import stripe

        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
            event_type = event["type"]
            sub_data = event["data"]["object"]
            event_id = event.get("id", "")
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            raise HTTPException(status_code=400, detail=_("error.webhook-verification-failed").format(error=e)) from e

        # Idempotency check — skip if already processed
        from ...services.webhook_base import dead_letter, is_already_processed, mark_processed

        if is_already_processed(db, "stripe", event_id):
            logger.info("Duplicate Stripe event %s (%s) — skipping", event_id, event_type)
            return {"received": True, "duplicate": True}

        if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            try:
                handle_subscription_updated(sub_data)
                mark_processed(db, "stripe", event_id, event_type, {"event_type": event_type, "data": sub_data})
                # Send receipt on new subscription
                if event_type == "customer.subscription.created":
                    customer_id = sub_data.get("customer", "")
                    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
                    if user:
                        send_receipt(
                            user.email,
                            user.subscription_tier.value,
                            int(cast(float, PRICING.get(user.subscription_tier, {}).get("price", 0))),
                        )
            except Exception as e:
                dead_letter(db, "stripe", event_id, event_type, {"event_type": event_type}, str(e))
                raise

        elif event_type == "invoice.payment_succeeded":
            customer_id = sub_data.get("customer", "")
            user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if user:
                lines = sub_data.get("lines", {}).get("data", [])
                tier = next(
                    (
                        line["description"]
                        for line in lines
                        if "subscription" in (line.get("description", "") or "").lower()
                    ),
                    "Pro",
                )
                amount = sub_data.get("amount_paid", 0) // 100
                invoice_url = sub_data.get("hosted_invoice_url", "")
                send_receipt(user.email, tier, amount, invoice_url)
            mark_processed(db, "stripe", event_id, event_type, {"event_type": event_type})

        elif event_type == "invoice.payment_failed":
            customer_id = sub_data.get("customer", "")
            if customer_id:
                handle_failed_payment(customer_id)
            mark_processed(db, "stripe", event_id, event_type, {"event_type": event_type})

        else:
            mark_processed(db, "stripe", event_id, event_type, {"event_type": event_type})

        return {"received": True}
    finally:
        db.close()


@router.get("/billing/invoices")
def billing_invoices(user: User = Depends(get_current_user)):
    """Retrieve invoice history from Stripe."""
    if not HAS_STRIPE or not user.stripe_customer_id:
        return {"invoices": []}
    try:
        import stripe

        invoice_list = stripe.Invoice.list(customer=user.stripe_customer_id, limit=12)
        return {
            "invoices": [
                {
                    "id": inv.id,
                    "amount_paid": inv.amount_paid,
                    "status": inv.status,
                    "created": inv.created,
                    "hosted_invoice_url": inv.hosted_invoice_url,
                    "invoice_pdf": inv.invoice_pdf,
                }
                for inv in invoice_list.data
            ]
        }
    except Exception as e:
        logger.error("Failed to fetch invoices: %s", e)
        return {"invoices": [], "error": str(e)}


@router.get("/billing/status")
def billing_status(user: User = Depends(get_current_user)):
    pricing = get_pricing_info()
    current_tier_info = pricing.get(user.subscription_tier.value, {})
    from ...services.trial import is_trial_active

    return {
        "tier": user.subscription_tier.value,
        "credits_used": user.credits_used_month,
        "credits_limit": current_tier_info.get("credits", 0),
        "stripe_customer_id": bool(user.stripe_customer_id),
        "stripe_subscription_id": bool(user.stripe_subscription_id),
        "trial_active": is_trial_active(user),
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        "dunning_count": user.dunning_count or 0,
    }
