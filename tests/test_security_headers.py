"""Tests for security middleware and response headers."""


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
    assert "frame-ancestors 'none'" in resp.headers.get("Content-Security-Policy", "")
    assert resp.headers.get("Strict-Transport-Security") is not None


def test_security_headers_on_error(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_cors_headers(client):
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert resp.headers.get("Access-Control-Allow-Origin") is not None


def test_request_id_present(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Request-ID") is not None


def test_request_id_preserved(client):
    req_id = "test-req-id-12345"
    resp = client.get("/health", headers={"X-Request-ID": req_id})
    assert resp.headers.get("X-Request-ID") == req_id


def test_security_headers_on_404(client):
    resp = client.get("/nonexistent-endpoint-12345")
    assert resp.status_code == 404
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"