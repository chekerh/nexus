import os
import shutil
import pathlib
import json

from backend.app.core.publisher import publish_clip
from backend.app.core.security import encrypt_token
from backend.app.models.account import SocialAccount


def test_publish_mock(client, db, test_user, auth_headers, tmp_path, monkeypatch):
    # Enable dev mock
    monkeypatch.setenv("DEV_PUBLISH_MOCK", "true")

    # Ensure upload dir exists and create a small dummy clip
    upload_dir = os.environ.get("UPLOAD_DIR")
    clips_dir = pathlib.Path(upload_dir) / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_path = clips_dir / "sample.mp4"
    clip_path.write_bytes(b"dummy-video-bytes")

    # Create a social account for the test user
    user_obj, _ = test_user
    account = SocialAccount(
        user_id=user_obj.id,
        platform="youtube",
        account_name="Dev YouTube",
        oauth_refresh_token_enc=encrypt_token("") if False else "",
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    payload = {
        "platform": "youtube",
        "account_id": account.id,
        "clip_filename": "sample.mp4",
        "title": "Integration Test",
        "description": "Testing dev publish mock",
    }

    resp = client.post("/api/v1/publish", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "publish" in data
    result = data["publish"]["result"]
    assert result.get("status") == "published"
    assert result.get("result_url")
    assert "mock" in result.get("video_url")

    # Ensure publish log was written
    log_path = os.environ.get("PUBLISH_LOG_PATH") or None
    if not log_path:
        # fallback to settings default
        from backend.app.core.config import settings

        log_path = settings.PUBLISH_LOG_PATH
    assert os.path.exists(log_path)
    with open(log_path) as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    assert any("Dev YouTube" in l or "Integration Test" in l for l in lines)


def test_publish_uses_system_credentials_when_account_has_none(monkeypatch, tmp_path):
    monkeypatch.setenv("DEV_PUBLISH_MOCK", "false")

    clip_path = tmp_path / "sample.mp4"
    clip_path.write_bytes(b"dummy")

    monkeypatch.setattr("backend.app.core.publisher.settings.SYSTEM_YOUTUBE_REFRESH_TOKEN", "system-refresh-token")
    monkeypatch.setattr("backend.app.core.publisher.settings.YOUTUBE_CLIENT_ID", "youtube-client")
    monkeypatch.setattr("backend.app.core.publisher.settings.YOUTUBE_CLIENT_SECRET", "youtube-secret")

    monkeypatch.setattr("backend.app.core.publisher._youtube_access_token", lambda *_args, **_kwargs: "system-access-token")
    monkeypatch.setattr("backend.app.core.publisher._youtube_upload_video", lambda **kwargs: "system-video-id")

    result = publish_clip(
        platform="youtube",
        account={"account_name": "System account"},
        video_path=str(clip_path),
        title="System credentials test",
        description="Uses the configured system credentials",
    )

    assert result.get("status") == "published"
    assert result.get("video_id") == "system-video-id"
    assert result.get("video_url") == "https://www.youtube.com/watch?v=system-video-id"
    assert result.get("auth_source") == "system"
