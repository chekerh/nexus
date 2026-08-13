"""Whop business logic — provision accounts, apply tiers, handle events."""

import json
import logging

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.whop import map_product_to_tier
from ..models.user import SubscriptionTier, User
from ..models.whop import WhopEvent, WhopLicense

logger = logging.getLogger("nexus.whop")


def provision_license(
    db: Session,
    user_id: str,
    license_key: str,
    product_id: str,
    purchase_id: str = "",
    customer_id: str = "",
) -> WhopLicense:
    """Create or update a license for a user."""
    tier = map_product_to_tier(product_id)
    if not tier:
        tier = "pro"

    existing = db.query(WhopLicense).filter(WhopLicense.license_key == license_key).first()
    if existing:
        existing.status = "active"
        existing.tier = tier
        existing.product_id = product_id
        existing.whop_purchase_id = purchase_id or existing.whop_purchase_id
        existing.whop_customer_id = customer_id or existing.whop_customer_id
        db.commit()
        db.refresh(existing)
        return existing

    license = WhopLicense(
        user_id=user_id,
        license_key=license_key,
        product_id=product_id,
        tier=tier,
        status="active",
        whop_purchase_id=purchase_id,
        whop_customer_id=customer_id,
    )
    db.add(license)
    db.commit()
    db.refresh(license)
    return license


def apply_tier_to_user(db: Session, user: User, tier: str):
    """Apply a subscription tier to a user with appropriate credits."""
    tier_enum = SubscriptionTier.PRO if tier == "pro" else SubscriptionTier.ENTERPRISE
    user.subscription_tier = tier_enum
    if tier == "pro":
        user.credits_limit_month = 50
    elif tier == "enterprise":
        user.credits_limit_month = 500
    db.commit()


def process_purchase_created(payload: dict) -> bool:
    """Process a whop purchase.created webhook event."""
    try:
        data = payload.get("data", {})
        purchase_id = data.get("id", "")
        product_id = data.get("product_id", "")
        license_key = data.get("license_key", "")
        user_data = data.get("user", {})
        customer_id = user_data.get("id", "")
        email = user_data.get("email", "")

        if not product_id or not license_key:
            logger.warning(f"Incomplete purchase webhook: {payload}")
            return False

        db = SessionLocal()
        try:
            tier = map_product_to_tier(product_id)
            if not tier:
                logger.info(f"Unknown product {product_id} — skipping")
                return False

            user = db.query(User).filter(User.email == email).first() if email else None
            if not user and email:
                user = User(
                    email=email,
                    password_hash="",
                    password_salt="",
                    display_name=email.split("@")[0],
                    subscription_tier=SubscriptionTier.FREE,
                    credits_limit_month=5,
                )
                db.add(user)
                db.flush()
                logger.info(f"Created user {user.id} from Whop purchase ({email})")

            if user:
                provision_license(db, user.id, license_key, product_id, purchase_id, customer_id)
                apply_tier_to_user(db, user, tier)
                logger.info(f"Provisioned {tier} for user {user.id} via Whop purchase {purchase_id}")

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Purchase provisioning failed: {e}")
            return False
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Process purchase.created failed: {e}")
        return False


def process_subscription_updated(payload: dict) -> bool:
    """Handle subscription updates from Whop."""
    try:
        data = payload.get("data", {})
        purchase_id = data.get("id", "")
        status = data.get("status", "")
        product_id = data.get("product_id", "")

        db = SessionLocal()
        try:
            license = db.query(WhopLicense).filter(WhopLicense.whop_purchase_id == purchase_id).first()
            if not license:
                logger.warning(f"No license found for purchase {purchase_id}")
                return False

            if status in ("cancelled", "expired", "revoked"):
                license.status = status
                user = db.query(User).filter(User.id == license.user_id).first()
                if user:
                    user.subscription_tier = SubscriptionTier.FREE
                    user.credits_limit_month = 5
            elif status == "active":
                license.status = "active"
                tier = map_product_to_tier(product_id)
                if tier:
                    license.tier = tier
                    user = db.query(User).filter(User.id == license.user_id).first()
                    if user:
                        apply_tier_to_user(db, user, tier)

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Subscription update failed: {e}")
            return False
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Process subscription.updated failed: {e}")
        return False


def log_event(event_type: str, whop_event_id: str, payload: dict):
    """Log a Whop event for audit trail."""
    db = SessionLocal()
    try:
        existing = (
            db.query(WhopEvent).filter(WhopEvent.whop_event_id == whop_event_id).first() if whop_event_id else None
        )
        if existing:
            return
        event = WhopEvent(
            event_type=event_type,
            whop_event_id=whop_event_id,
            payload=json.dumps(payload),
            processed=True,
        )
        db.add(event)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log Whop event: {e}")
    finally:
        db.close()
