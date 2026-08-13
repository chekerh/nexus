"""Auth API tests."""


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_register_and_login(client):
    email = "newuser@test.com"
    password = "SecurePass123!"
    name = "New User"

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": name,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == email
    assert data["user"]["display_name"] == name

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == email


def test_login_invalid_password(client, test_user):
    user, _ = test_user
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "wrongpassword",
        },
    )
    assert resp.status_code == 401


def test_me_endpoint(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_register_with_duplicate_email(client, test_user):
    user, _ = test_user
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": user.email,
            "password": "AnotherPass1!",
            "display_name": "Duplicate",
        },
    )
    assert resp.status_code == 409


def test_csrf_token(client):
    resp = client.get("/api/v1/auth/csrf-token")
    assert resp.status_code == 200
    data = resp.json()
    assert "csrf_token" in data
    assert len(data["csrf_token"]) == 64


def test_create_and_use_api_key(client, auth_headers):
    resp = client.post("/api/v1/auth/api-keys", json={"name": "test-key"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"].startswith("nex_")

    raw_key = data["api_key"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_list_api_keys(client, auth_headers):
    client.post("/api/v1/auth/api-keys", json={"name": "key-1"}, headers=auth_headers)
    client.post("/api/v1/auth/api-keys", json={"name": "key-2"}, headers=auth_headers)

    resp = client.get("/api/v1/auth/api-keys", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["api_keys"]) == 2


def test_revoke_api_key(client, auth_headers):
    resp = client.post("/api/v1/auth/api-keys", json={"name": "revoke-me"}, headers=auth_headers)
    key_id = resp.json()["id"]
    raw_key = resp.json()["api_key"]

    client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=auth_headers)

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw_key}"})
    assert resp.status_code == 401
