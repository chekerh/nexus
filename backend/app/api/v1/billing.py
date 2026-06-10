"""Billing and subscription API."""
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.user import User, SubscriptionTier
from ...services.billing import (
    create_checkout_session, handle_subscription_updated, get_pricing_info,
)
from ..deps import get_current_user

router = APIRouter(tags=["billing"])


class CheckoutRequest(BaseModel):
    tier: str


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
        raise HTTPException(status_code=400, detail="Invalid tier")

    result = create_checkout_session(user, tier)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint for subscription events."""
    payload = await request.body()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = data.get("type", "")
    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        sub_data = data.get("data", {}).get("object", {})
        handle_subscription_updated(sub_data)

    return {"received": True}


@router.get("/billing/status")
def billing_status(user: User = Depends(get_current_user)):
    pricing = get_pricing_info()
    current_tier_info = pricing.get(user.subscription_tier.value, {})
    return {
        "tier": user.subscription_tier.value,
        "credits_used": user.credits_used_month,
        "credits_limit": current_tier_info.get("credits", 0),
        "stripe_customer_id": bool(user.stripe_customer_id),
        "stripe_subscription_id": bool(user.stripe_subscription_id),
    }
