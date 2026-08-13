"""Whop API client — license validation, webhook signature verification."""

import hashlib
import hmac
import logging

import httpx

from .config import settings

logger = logging.getLogger("nexus.whop")

WHOP_API_BASE = "https://api.whop.com/v1"


def _headers() -> dict:
    api_key = (settings.WHOP_API_KEY or "").strip()
    if not api_key:
        logger.warning("WHOP_API_KEY not configured")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 webhook signature."""
    secret = (settings.WHOP_WEBHOOK_SECRET or "").strip()
    if not secret:
        logger.warning("WHOP_WEBHOOK_SECRET not configured — skipping signature verification")
        return True
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def validate_license_key(license_key: str) -> dict | None:
    """Validate a license key with Whop API.

    Returns the license data dict if valid, None if invalid/error.
    """
    api_key = (settings.WHOP_API_KEY or "").strip()
    if not api_key:
        logger.warning("Cannot validate license: WHOP_API_KEY not configured")
        return None

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{WHOP_API_BASE}/licenses/validate",
                headers=_headers(),
                json={"license_key": license_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data") or data
            logger.warning(f"License validation failed ({resp.status_code}): {resp.text[:300]}")
            return None
    except Exception as e:
        logger.error(f"License validation error: {e}")
        return None


def fetch_purchase(purchase_id: str) -> dict | None:
    """Fetch purchase details from Whop."""
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{WHOP_API_BASE}/purchases/{purchase_id}",
                headers=_headers(),
            )
            if resp.status_code == 200:
                return resp.json().get("data") or resp.json()
            return None
    except Exception as e:
        logger.error(f"Fetch purchase error: {e}")
        return None


TIER_MAP = {
    "pro": "pro",
    "enterprise": "enterprise",
}


def map_product_to_tier(product_id: str) -> str | None:
    """Map a Whop product ID to a subscription tier."""
    pro_id = (settings.WHOP_PRO_PRODUCT_ID or "").strip()
    enterprise_id = (settings.WHOP_ENTERPRISE_PRODUCT_ID or "").strip()
    if pro_id and product_id == pro_id:
        return "pro"
    if enterprise_id and product_id == enterprise_id:
        return "enterprise"
    return None
