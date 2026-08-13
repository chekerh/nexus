"""
Publishing Integration Tests.
Tests the publish flow: account lookup, fallback behavior, and worker loop.
Run: python -m pytest scripts/test_publish.py -v
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ["DATABASE_URL"] = ""
os.environ["JWT_SECRET"] = "test-secret"
os.environ["YOUTUBE_CLIENT_ID"] = ""
os.environ["YOUTUBE_CLIENT_SECRET"] = ""
os.environ["TIKTOK_CLIENT_KEY"] = ""
os.environ["TIKTOK_CLIENT_SECRET"] = ""

from app.core.publisher import (
    publish_clip,
    _publish_to_youtube,
    _publish_to_tiktok,
    _publish_to_instagram,
    MANUAL_UPLOAD_URL,
    SUPPORTED_PLATFORMS,
)


def test_supported_platforms():
    """All expected platforms are supported."""
    assert "youtube" in SUPPORTED_PLATFORMS
    assert "tiktok" in SUPPORTED_PLATFORMS
    assert "instagram" in SUPPORTED_PLATFORMS
    assert "twitter" in SUPPORTED_PLATFORMS
    assert "facebook" in SUPPORTED_PLATFORMS
    assert "linkedin" in SUPPORTED_PLATFORMS


def test_unsupported_platform():
    """Unsupported platform returns error."""
    result = publish_clip("myspace", {}, "/fake/path.mp4", "Title", "Desc")
    assert result["status"] == "error"
    assert "unsupported" in result["error"].lower()


def test_publish_youtube_no_credentials():
    """YouTube publish returns manual_required when no credentials."""
    result = _publish_to_youtube({}, "/fake/path.mp4", "Title", "Desc")
    assert result["status"] == "manual_required"
    assert "refresh token" in result["reason"].lower()
    assert result["upload_url"] == MANUAL_UPLOAD_URL["youtube"]


def test_publish_youtube_no_refresh_token():
    """YouTube returns manual when account has no refresh token."""
    account = {"oauth_refresh_token": ""}
    result = _publish_to_youtube(account, "/fake/path.mp4", "Title", "Desc")
    assert result["status"] == "manual_required"
    assert "refresh token" in result["reason"].lower()


def test_publish_tiktok_no_credentials():
    """TikTok publish returns manual_required when no client credentials."""
    result = _publish_to_tiktok({}, "/fake/path.mp4", "Title", "Desc")
    assert result["status"] == "manual_required"
    assert "TIKTOK_CLIENT_KEY" in result["reason"]
    assert result["upload_url"] == MANUAL_UPLOAD_URL["tiktok"]


def test_publish_instagram_no_credentials():
    """Instagram publish returns manual_required without user_id/token."""
    result = _publish_to_instagram({}, "/fake/path.mp4", "Title", "Desc")
    assert result["status"] == "manual_required"
    assert "instagram_user_id" in result["reason"].lower()
    assert result["upload_url"] == MANUAL_UPLOAD_URL["instagram"]


def test_publish_clip_returns_manual_url():
    """publish_clip returns manual_required with upload URL for unconfigured platforms."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"fake video content")
        video_path = f.name
    try:
        for platform in ["youtube", "tiktok", "instagram"]:
            result = publish_clip(platform, {}, video_path, "Title", "Desc")
            assert result["status"] == "manual_required"
            assert result["upload_url"] == MANUAL_UPLOAD_URL[platform]
            assert "title" in result
            assert result["title"] == "Title"
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)


def test_publish_history_store():
    """PublishHistoryStore reads and writes correctly."""
    from app.core.publisher import PublishHistoryStore
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("[]")
        db_path = f.name
    try:
        store = PublishHistoryStore(db_path)
        assert store.list() == []

        entry = store.append({"platform": "test", "status": "ok"})
        assert entry["platform"] == "test"
        assert len(store.list()) == 1

        store.append({"platform": "test2", "status": "ok"})
        assert len(store.list()) == 2
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_all_platforms_have_manual_urls():
    """Every supported platform has a manual upload URL."""
    for platform in SUPPORTED_PLATFORMS:
        assert platform in MANUAL_UPLOAD_URL
        assert MANUAL_UPLOAD_URL[platform].startswith("https://")


if __name__ == "__main__":
    test_supported_platforms()
    print("✓ test_supported_platforms")
    test_unsupported_platform()
    print("✓ test_unsupported_platform")
    test_publish_youtube_no_credentials()
    print("✓ test_publish_youtube_no_credentials")
    test_publish_youtube_no_refresh_token()
    print("✓ test_publish_youtube_no_refresh_token")
    test_publish_tiktok_no_credentials()
    print("✓ test_publish_tiktok_no_credentials")
    test_publish_instagram_no_credentials()
    print("✓ test_publish_instagram_no_credentials")
    test_publish_clip_returns_manual_url()
    print("✓ test_publish_clip_returns_manual_url")
    test_publish_history_store()
    print("✓ test_publish_history_store")
    test_all_platforms_have_manual_urls()
    print("✓ test_all_platforms_have_manual_urls")
    print("\n🎉 All publishing tests passed!")
