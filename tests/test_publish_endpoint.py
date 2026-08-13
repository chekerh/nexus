"""Tests for publishing API endpoint validation and security."""

import os

from backend.app.models.account import SocialAccount
from backend.app.models.publish_history import PublishHistory


def test_publish_endpoint_requires_auth(client):
    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "youtube",
            "account_id": "test",
            "clip_filename": "test.mp4",
            "title": "Test",
            "description": "Test",
        },
    )
    assert resp.status_code == 401


def test_publish_unsupported_platform(client, auth_headers):
    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "invalid_platform",
            "account_id": "test",
            "clip_filename": "test.mp4",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_publish_path_traversal_blocked(client, auth_headers, db, test_user):
    """Path traversal in clip_filename should be rejected."""
    user, _ = test_user
    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "youtube",
            "account_id": "test",
            "clip_filename": "../etc/passwd",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_publish_with_absolute_path_blocked(client, auth_headers):
    """Absolute paths in clip_filename should be rejected."""
    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "youtube",
            "account_id": "test",
            "clip_filename": "/etc/passwd",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_publish_account_not_found(client, auth_headers):
    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "youtube",
            "account_id": "nonexistent-account-id",
            "clip_filename": "test.mp4",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_publish_platform_mismatch(client, auth_headers, db, test_user):
    """Account platform must match the requested platform."""
    user, _ = test_user
    account = SocialAccount(
        user_id=user.id,
        platform="tiktok",
        account_name="TikTok Account",
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "youtube",
            "account_id": account.id,
            "clip_filename": "test.mp4",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_publish_history_empty(client, auth_headers):
    """Publish history should be empty for new user."""
    resp = client.get("/api/v1/publish/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["history"] == []


def test_publish_history_requires_auth(client):
    resp = client.get("/api/v1/publish/history")
    assert resp.status_code == 401


def test_publish_mock_creates_history_entry(client, auth_headers, db, test_user, monkeypatch):
    """Publishing in mock mode should create a history entry."""
    monkeypatch.setenv("DEV_PUBLISH_MOCK", "true")

    user, _ = test_user
    account = SocialAccount(
        user_id=user.id,
        platform="youtube",
        account_name="Test YouTube",
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    upload_dir = os.environ.get("UPLOAD_DIR")
    clips_dir = os.path.join(upload_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    clip_path = os.path.join(clips_dir, "history_test.mp4")
    with open(clip_path, "wb") as f:
        f.write(b"dummy")

    resp = client.post(
        "/api/v1/publish",
        json={
            "platform": "youtube",
            "account_id": account.id,
            "clip_filename": "history_test.mp4",
            "title": "History Test",
            "description": "Test description",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Verify history entry was created
    history = db.query(PublishHistory).filter(PublishHistory.user_id == user.id).all()
    assert len(history) == 1
    assert history[0].platform == "youtube"
    assert history[0].title == "History Test"
    assert history[0].result["status"] == "published"
