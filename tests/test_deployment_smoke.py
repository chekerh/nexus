"""Deployment smoke tests."""


def test_smoke_health_and_pricing(client):
    health = client.get("/health")
    pricing = client.get("/api/v1/pricing")

    assert health.status_code == 200
    assert pricing.status_code == 200
    assert set(pricing.json().keys()) >= {"free", "pro", "enterprise"}


def test_smoke_authenticated_status_endpoints(client, auth_headers):
    billing = client.get("/api/v1/billing/status", headers=auth_headers)
    whop = client.get("/api/v1/whop/status", headers=auth_headers)

    assert billing.status_code == 200
    assert whop.status_code == 200
    assert billing.json()["tier"] == "free"
    assert whop.json()["has_license"] is False