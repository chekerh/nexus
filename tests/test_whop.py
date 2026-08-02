"""Whop integration tests."""

import json

from backend.app.models.user import SubscriptionTier, User
from backend.app.models.whop import WhopLicense


def test_whop_validate_applies_tier(client, auth_headers, db, test_user, monkeypatch):
    monkeypatch.setattr("backend.app.api.v1.whop.map_product_to_tier", lambda product_id: "pro")
    monkeypatch.setattr(
        "backend.app.api.v1.whop.validate_license_key",
        lambda license_key: {"id": "purchase-1", "status": "active", "product_id": "product-pro", "user": {"id": "customer-1"}},
    )

    resp = client.post("/api/v1/whop/validate", json={"license_key": "whop-abc"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["tier"] == "pro"

    user, _ = test_user
    db.refresh(user)
    assert user.subscription_tier == SubscriptionTier.PRO
    license_row = db.query(WhopLicense).filter(WhopLicense.user_id == user.id).first()
    assert license_row is not None
    assert license_row.status == "active"


def test_whop_claim_creates_user_and_token(client, db, monkeypatch):
    monkeypatch.setattr("backend.app.api.v1.whop.map_product_to_tier", lambda product_id: "enterprise")
    monkeypatch.setattr(
        "backend.app.api.v1.whop.validate_license_key",
        lambda license_key: {"id": "purchase-2", "status": "active", "product_id": "product-enterprise", "user": {"id": "customer-2"}},
    )

    resp = client.post(
        "/api/v1/whop/claim",
        json={"license_key": "whop-enterprise", "email": "whop@example.com", "password": "secret123", "display_name": "Whop User"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is True
    assert data["tier"] == "enterprise"
    assert data["token"]

    user = db.query(User).filter(User.email == "whop@example.com").first()
    assert user is not None
    assert user.subscription_tier == SubscriptionTier.ENTERPRISE


def test_whop_webhook_purchase_provisions_account(client, db, monkeypatch):
    payload = {
        "type": "purchase.created",
        "data": {
            "id": "whop-purchase-1",
            "product_id": "product-pro",
            "license_key": "license-xyz",
            "user": {"id": "customer-123", "email": "whop-purchase@example.com"},
        },
    }
    monkeypatch.setattr("backend.app.services.whop.map_product_to_tier", lambda product_id: "pro")

    resp = client.post(
        "/api/v1/whop/webhook",
        content=json.dumps(payload).encode("utf-8"),
        headers={"X-Whop-Signature": "ignored", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["processed"] is True

    user = db.query(User).filter(User.email == "whop-purchase@example.com").first()
    assert user is not None
    assert user.subscription_tier == SubscriptionTier.PRO
