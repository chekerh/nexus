"""OAuth integration tests."""

from backend.app.api.v1.oauth import settings as oauth_settings
from backend.app.core.security import decrypt_token
from backend.app.models.account import SocialAccount


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_youtube_authorize_returns_provider_url(client, auth_headers, monkeypatch):
    monkeypatch.setattr(oauth_settings, "YOUTUBE_CLIENT_ID", "youtube-client")
    monkeypatch.setattr(oauth_settings, "YOUTUBE_CLIENT_SECRET", "youtube-secret")

    resp = client.get("/api/v1/oauth/youtube/authorize", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "redirect_uri=" in data["url"]
    assert data["state"]


def test_youtube_callback_persists_tokens(client, auth_headers, db, test_user, monkeypatch):
    monkeypatch.setattr(oauth_settings, "YOUTUBE_CLIENT_ID", "youtube-client")
    monkeypatch.setattr(oauth_settings, "YOUTUBE_CLIENT_SECRET", "youtube-secret")

    user, _ = test_user
    auth_resp = client.get("/api/v1/oauth/youtube/authorize", headers=auth_headers)
    state = auth_resp.json()["state"]

    def fake_post(url, data=None, timeout=None, **kwargs):
        assert "oauth2.googleapis.com/token" in url
        return _FakeResponse({"access_token": "yt-access", "refresh_token": "yt-refresh"})

    def fake_get(url, headers=None, timeout=None, **kwargs):
        assert "youtube/v3/channels" in url
        return _FakeResponse({"items": [{"snippet": {"title": "Test Channel"}}]})

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    resp = client.get(f"/api/v1/oauth/youtube/callback?code=test-code&state={state}")
    assert resp.status_code == 200

    account = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user.id, SocialAccount.platform == "youtube").first()
    )
    assert account is not None
    assert account.account_name == "Test Channel"
    assert decrypt_token(account.oauth_refresh_token_enc) == "yt-refresh"


def test_tiktok_authorize_returns_provider_url(client, auth_headers, monkeypatch):
    monkeypatch.setattr(oauth_settings, "TIKTOK_CLIENT_KEY", "tiktok-client")

    resp = client.get("/api/v1/oauth/tiktok/authorize", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("https://www.tiktok.com/v2/auth/authorize?")
    assert data["state"]
