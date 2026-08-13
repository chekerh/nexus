"""Whop integration API — webhook receiver, license validation, status."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.i18n import _
from ...core.middleware import hash_password
from ...core.whop import map_product_to_tier, validate_license_key, verify_webhook_signature
from ...models.user import SubscriptionTier, User
from ...models.whop import WhopLicense
from ...services.webhook_base import is_already_processed, mark_processed
from ...services.whop import (
    apply_tier_to_user,
    log_event,
    process_purchase_created,
    process_subscription_updated,
    provision_license,
)
from ..deps import get_current_user
from .auth import _create_jwt

logger = logging.getLogger("nexus.whop")
router = APIRouter(tags=["whop"])


class ClaimLicenseRequest(BaseModel):
    license_key: str
    email: str
    password: str
    display_name: str = ""


class ValidateLicenseRequest(BaseModel):
    license_key: str


@router.post("/whop/webhook")
async def whop_webhook(request: Request):
    """Receive Whop webhook events (purchase, subscription, license).

    Idempotency is enforced via WebhookEvent table before any business logic.
    """
    payload = await request.body()
    signature = request.headers.get("X-Whop-Signature", "")

    if not verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail=_("error.invalid-signature"))

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=_("error.invalid-json-payload")) from None

    event_type = data.get("type", "")
    event_data = data.get("data", {})
    event_id = event_data.get("id", "") if isinstance(event_data, dict) else ""

    logger.info(f"Whop webhook: {event_type}")

    # Idempotency check — run BEFORE any business logic
    db = next(get_db())
    try:
        if is_already_processed(db, "whop", event_id):
            logger.info("Duplicate Whop event %s (%s) — skipping", event_id, event_type)
            return {"received": True, "duplicate": True}

        if event_type == "purchase.created":
            success = process_purchase_created(data)
            mark_processed(db, "whop", event_id, event_type, data)
            log_event(event_type, event_id, data)
            return {"received": True, "processed": success}

        elif event_type in ("subscription.updated", "subscription.cancelled"):
            success = process_subscription_updated(data)
            mark_processed(db, "whop", event_id, event_type, data)
            return {"received": True, "processed": success}

        elif event_type in ("purchase.refunded", "license.revoked"):
            purchase_id = event_data.get("id", "") if isinstance(event_data, dict) else ""
            lic = (
                db.query(WhopLicense).filter(WhopLicense.whop_purchase_id == purchase_id).first()
                if purchase_id
                else None
            )
            if lic:
                lic.status = "revoked"
                user = db.query(User).filter(User.id == lic.user_id).first()
                if user:
                    user.subscription_tier = SubscriptionTier.FREE
                    user.credits_limit_month = 5
                db.commit()
            mark_processed(db, "whop", event_id, event_type, data)
            return {"received": True, "processed": True}

        logger.info(f"Unhandled Whop event type: {event_type}")
        return {"received": True, "processed": False}
    finally:
        db.close()


@router.post("/whop/validate")
def validate_license(
    payload: ValidateLicenseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate a license key against Whop and apply tier to current user."""
    result = validate_license_key(payload.license_key)
    if not result:
        raise HTTPException(status_code=400, detail=_("error.invalid-license-key"))

    product_id = result.get("product_id", "")
    status = result.get("status", "active")
    if status != "active":
        raise HTTPException(status_code=400, detail=_("error.license-status").format(status=status))

    tier = map_product_to_tier(product_id)
    if not tier:
        raise HTTPException(status_code=400, detail=_("error.unknown-product"))

    provision_license(
        db,
        user.id,
        payload.license_key,
        product_id,
        purchase_id=result.get("id", ""),
        customer_id=result.get("user", {}).get("id", ""),
    )
    apply_tier_to_user(db, user, tier)

    return {
        "valid": True,
        "tier": tier,
        "license_key": payload.license_key,
    }


@router.post("/whop/claim")
def claim_license(
    payload: ClaimLicenseRequest,
    db: Session = Depends(get_db),
):
    """Claim a license key and create an account.

    Used when a user purchased on Whop but hasn't created an account yet.
    """
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail=_("error.email-taken-license"))

    result = validate_license_key(payload.license_key)
    if not result:
        raise HTTPException(status_code=400, detail=_("error.invalid-license-key"))

    status = result.get("status", "active")
    if status != "active":
        raise HTTPException(status_code=400, detail=_("error.license-status").format(status=status))

    product_id = result.get("product_id", "")
    tier = map_product_to_tier(product_id)
    if not tier:
        raise HTTPException(status_code=400, detail=_("error.unknown-product"))

    pw_hash, pw_salt = hash_password(payload.password)

    user = User(
        email=payload.email,
        password_hash=pw_hash,
        password_salt=pw_salt,
        display_name=payload.display_name or payload.email.split("@")[0],
        subscription_tier=SubscriptionTier.PRO if tier == "pro" else SubscriptionTier.ENTERPRISE,
    )
    if tier == "pro":
        user.credits_limit_month = 50
    elif tier == "enterprise":
        user.credits_limit_month = 500

    db.add(user)
    db.flush()

    provision_license(
        db,
        user.id,
        payload.license_key,
        product_id,
        purchase_id=result.get("id", ""),
        customer_id=result.get("user", {}).get("id", ""),
    )

    db.commit()
    db.refresh(user)

    token = _create_jwt(user.id)

    return {
        "created": True,
        "user_id": user.id,
        "tier": tier,
        "email": payload.email,
        "token": token,
    }


@router.get("/whop/status")
def whop_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the Whop license status for the current user."""
    license = (
        db.query(WhopLicense)
        .filter(
            WhopLicense.user_id == user.id,
            WhopLicense.status == "active",
        )
        .first()
    )
    return {
        "has_license": license is not None,
        "tier": user.subscription_tier.value,
        "license_key": license.license_key[-8:] if license else None,
        "status": license.status if license else None,
    }
