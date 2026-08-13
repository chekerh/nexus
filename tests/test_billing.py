"""Tests for billing and subscription API."""


def test_pricing_endpoint(client):
    resp = client.get("/api/v1/pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert data["free"]["price"] == 0
    assert data["pro"]["price"] == 29
    assert data["enterprise"]["price"] == 99


def test_trial_start_and_status(client, auth_headers):
    resp = client.post("/api/v1/billing/trial", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["credits_limit"] == 10
    assert data["trial_ends_at"]

    resp = client.get("/api/v1/billing/trial-status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trial_active"] is True
    assert data["trial_ends_at"] is not None


def test_trial_cannot_be_started_twice(client, auth_headers):
    client.post("/api/v1/billing/trial", headers=auth_headers)
    resp = client.post("/api/v1/billing/trial", headers=auth_headers)
    assert resp.status_code == 400


def test_trial_status_without_trial(client, auth_headers):
    resp = client.get("/api/v1/billing/trial-status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trial_active"] is False
    assert data["trial_ends_at"] is None


def test_billing_checkout_free_tier(client, auth_headers):
    resp = client.post("/api/v1/billing/checkout", json={"tier": "free"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["url"] is None


def test_billing_checkout_invalid_tier(client, auth_headers):
    resp = client.post("/api/v1/billing/checkout", json={"tier": "invalid-tier"}, headers=auth_headers)
    assert resp.status_code == 400


def test_billing_checkout_pro_mock(client, auth_headers):
    resp = client.post("/api/v1/billing/checkout", json={"tier": "pro"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"] == "/billing.html?checkout=success&mock=true"


def test_billing_status(client, auth_headers):
    resp = client.get("/api/v1/billing/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"
    assert data["credits_limit"] == 5
    assert data["trial_active"] is False


def test_billing_status_requires_auth(client):
    resp = client.get("/api/v1/billing/status")
    assert resp.status_code == 401


def test_billing_portal_dev_mode(client, auth_headers):
    resp = client.post("/api/v1/billing/portal", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["url"] == "/billing.html?portal=mock"


def test_billing_cancel_dev_mode(client, auth_headers):
    resp = client.post("/api/v1/billing/cancel", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"


def test_billing_invoices_dev_mode(client, auth_headers):
    resp = client.get("/api/v1/billing/invoices", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["invoices"] == []
