"""OAuth flows for connecting social media accounts — YouTube, TikTok, Instagram, X/Twitter.

Each platform has a two-step flow:
  1. GET /oauth/{platform}/authorize → returns the provider's OAuth URL
  2. GET /oauth/{platform}/callback → handles the redirect, stores tokens

Users click "Connect" in the frontend → popup opens → authorizes → tokens saved.
"""

import html
import secrets
import urllib.parse
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...core.security import encrypt_token
from ...models.account import SocialAccount
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(prefix="/oauth", tags=["oauth"])

from ...models.oauth_state import OAuthState  # noqa: F401 — ensure model is imported at module level


def _generate_state(user_id: str, platform: str, db: Session) -> str:
    state = secrets.token_urlsafe(32)
    record = OAuthState(
        state=state,
        user_id=user_id,
        platform=platform,
    )
    db.add(record)
    db.commit()
    return state


def _consume_state(state: str, db: Session) -> dict:
    record = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not record:
        raise HTTPException(status_code=400, detail=_("error.oauth-invalid-state"))
    db.delete(record)
    db.commit()
    return {
        "user_id": record.user_id,
        "platform": record.platform,
        "created": record.created_at,
        "code_verifier": record.code_verifier or "",
    }


def _frontend_origin() -> str:
    base = settings.PUBLIC_BASE_URL or "http://localhost:8000"
    # Strip path, keep origin
    from urllib.parse import urlparse

    parsed = urlparse(base)
    return f"{parsed.scheme}://{parsed.netloc}"


def _redirect_success(platform: str) -> HTMLResponse:
    origin = _frontend_origin()
    safe_platform = html.escape(platform)
    return HTMLResponse(f"""<!DOCTYPE html><html><body>
<script>window.opener.postMessage({{type:'oauth-callback',platform:'{safe_platform}',status:'success'}},'{origin}');window.close();</script>
<p>Connected! You can close this tab.</p></body></html>""")


def _redirect_error(message: str) -> HTMLResponse:
    origin = _frontend_origin()
    safe_message = html.escape(message)
    return HTMLResponse(f"""<!DOCTYPE html><html><body>
<script>window.opener.postMessage({{type:'oauth-callback',status:'error',message:'{safe_message}'}},'{origin}');window.close();</script>
<p>{safe_message}</p></body></html>""")


# ── YouTube OAuth ─────────────────────────────────────────────


@router.get("/youtube/authorize")
def youtube_authorize(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail=_("error.youtube-not-configured"),
        )
    state = _generate_state(user.id, "youtube", db)
    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/youtube/callback"
    params = urllib.parse.urlencode(
        {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
            "response_type": "code",
            "access_type": "offline",
            "state": state,
            "prompt": "consent",
        }
    )
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}", "state": state}


@router.get("/youtube/callback")
def youtube_callback(
    code: str = Query(""), state: str = Query(""), error: str = Query(None), db: Session = Depends(get_db)
):
    if error:
        return _redirect_error(_("error.oauth-youtube-cancelled").format(error=error))
    data = _consume_state(state, db)
    user_id = data["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect_error(_("error.user-not-found"))

    import requests

    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/youtube/callback"

    # Exchange code for tokens
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_data = resp.json()
        if "error" in token_data:
            return _redirect_error(_("error.oauth-token-exchange-failed").format(detail=token_data.get('error_description', token_data['error'])))
    except requests.RequestException as e:
        return _redirect_error(_("error.oauth-token-exchange-failed-detail").format(detail=e))

    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        return _redirect_error(_("error.oauth-no-refresh-token"))

    access_token = token_data.get("access_token", "")

    # Get channel + user info
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        chan_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=headers, timeout=10
        )
        chan_data = chan_resp.json()
        channel_name = "YouTube Channel"
        if "items" in chan_data and chan_data["items"]:
            channel_name = chan_data["items"][0]["snippet"]["title"]
    except requests.RequestException:
        channel_name = "YouTube Channel"

    # Store account
    existing = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user_id, SocialAccount.platform == "youtube").first()
    )
    if existing:
        existing.oauth_refresh_token_enc = encrypt_token(refresh_token)
        existing.account_name = channel_name
    else:
        account = SocialAccount(
            user_id=user_id,
            platform="youtube",
            account_name=channel_name,
            auth_mode="oauth",
            oauth_refresh_token_enc=encrypt_token(refresh_token),
        )
        db.add(account)
    db.commit()

    return _redirect_success("youtube")


# ── TikTok OAuth ──────────────────────────────────────────────


@router.get("/tiktok/authorize")
def tiktok_authorize(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.TIKTOK_CLIENT_KEY:
        raise HTTPException(status_code=400, detail=_("error.tiktok-not-configured"))
    state = _generate_state(user.id, "tiktok", db)
    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/tiktok/callback"
    params = urllib.parse.urlencode(
        {
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "redirect_uri": redirect_uri,
            "scope": "user.info.basic,video.upload,video.publish",
            "response_type": "code",
            "state": state,
        }
    )
    return {"url": f"https://www.tiktok.com/v2/auth/authorize?{params}", "state": state}


@router.get("/tiktok/callback")
def tiktok_callback(
    code: str = Query(""), state: str = Query(""), error: str = Query(None), db: Session = Depends(get_db)
):
    if error:
        return _redirect_error(_("error.oauth-tiktok-cancelled").format(error=error))
    data = _consume_state(state, db)
    user_id = data["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect_error(_("error.user-not-found"))

    import requests

    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/tiktok/callback"

    try:
        resp = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        token_data = resp.json()
        if "error" in token_data:
            return _redirect_error(_("error.oauth-token-exchange-failed").format(detail=token_data.get('error_description', token_data['error'])))
    except requests.RequestException as e:
        return _redirect_error(_("error.oauth-token-exchange-failed-detail").format(detail=e))

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    open_id = token_data.get("open_id", "")

    # Get user info
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        info_resp = requests.get(
            "https://open.tiktokapis.com/v2/user/info/?fields=display_name", headers=headers, timeout=10
        )
        info_data = info_resp.json()
        display_name = info_data.get("data", {}).get("user", {}).get("display_name", "TikTok Account")
    except requests.RequestException:
        display_name = "TikTok Account"

    existing = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user_id, SocialAccount.platform == "tiktok").first()
    )
    if existing:
        existing.tiktok_access_token_enc = encrypt_token(access_token)
        existing.tiktok_refresh_token_enc = encrypt_token(refresh_token)
        existing.tiktok_open_id = open_id
        existing.account_name = display_name
    else:
        account = SocialAccount(
            user_id=user_id,
            platform="tiktok",
            account_name=display_name,
            auth_mode="oauth",
            tiktok_access_token_enc=encrypt_token(access_token),
            tiktok_refresh_token_enc=encrypt_token(refresh_token),
            tiktok_open_id=open_id,
        )
        db.add(account)
    db.commit()

    return _redirect_success("tiktok")


# ── Instagram OAuth ───────────────────────────────────────────


@router.get("/instagram/authorize")
def instagram_authorize(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.FACEBOOK_CLIENT_ID or not settings.FACEBOOK_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail=_("error.instagram-not-configured"),
        )
    state = _generate_state(user.id, "instagram", db)
    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/instagram/callback"
    params = urllib.parse.urlencode(
        {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list",
            "response_type": "code",
            "state": state,
        }
    )
    return {"url": f"https://www.facebook.com/v22.0/dialog/oauth?{params}", "state": state}


@router.get("/instagram/callback")
def instagram_callback(
    code: str = Query(""), state: str = Query(""), error: str = Query(None), db: Session = Depends(get_db)
):
    if error:
        return _redirect_error(_("error.oauth-instagram-cancelled").format(error=error))
    data = _consume_state(state, db)
    user_id = data["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect_error(_("error.user-not-found"))

    import requests

    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/instagram/callback"

    try:
        resp = requests.post(
            "https://graph.facebook.com/v22.0/oauth/access_token",
            data={
                "client_id": settings.FACEBOOK_CLIENT_ID,
                "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        token_data = resp.json()
        if "error" in token_data:
            return _redirect_error(_("error.oauth-token-exchange-failed").format(detail=token_data.get('error', {}).get('message', str(token_data))))
    except requests.RequestException as e:
        return _redirect_error(_("error.oauth-token-exchange-failed-detail").format(detail=e))

    access_token = token_data.get("access_token", "")

    # Get Instagram Business accounts
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        pages_resp = requests.get(
            "https://graph.facebook.com/v22.0/me/accounts?fields=id,name,instagram_business_account",
            headers=headers,
            timeout=10,
        )
        pages_data = pages_resp.json()
        ig_account_id = ""
        account_name = "Instagram Account"
        if "data" in pages_data and pages_data["data"]:
            for page in pages_data["data"]:
                if "instagram_business_account" in page:
                    ig_account_id = page["instagram_business_account"]["id"]
                    account_name = page["name"]
                    break
    except requests.RequestException:
        pass

    existing = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user_id, SocialAccount.platform == "instagram").first()
    )
    if existing:
        existing.instagram_access_token_enc = encrypt_token(access_token)
        existing.instagram_user_id = ig_account_id
        existing.account_name = account_name
    else:
        account = SocialAccount(
            user_id=user_id,
            platform="instagram",
            account_name=account_name,
            auth_mode="oauth",
            instagram_access_token_enc=encrypt_token(access_token),
            instagram_user_id=ig_account_id,
        )
        db.add(account)
    db.commit()

    return _redirect_success("instagram")


# ── X/Twitter OAuth 2.0 ───────────────────────────────────────


@router.get("/twitter/authorize")
def twitter_authorize(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.TWITTER_CLIENT_ID:
        raise HTTPException(status_code=400, detail=_("error.twitter-not-configured"))
    state = _generate_state(user.id, "twitter", db)
    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/twitter/callback"
    code_verifier = secrets.token_urlsafe(64)
    db.query(OAuthState).filter(OAuthState.state == state).update({"code_verifier": code_verifier})
    db.commit()

    import base64
    import hashlib

    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()

    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.TWITTER_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "tweet.read tweet.write users.read offline.access",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return {"url": f"https://twitter.com/i/oauth2/authorize?{params}", "state": state}


@router.get("/twitter/callback")
def twitter_callback(
    code: str = Query(""), state: str = Query(""), error: str = Query(None), db: Session = Depends(get_db)
):
    if error:
        return _redirect_error(_("error.oauth-twitter-cancelled").format(error=error))
    data = _consume_state(state, db)
    user_id = data["user_id"]
    code_verifier = data.get("code_verifier", "")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect_error(_("error.user-not-found"))

    import requests

    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/twitter/callback"

    try:
        resp = requests.post(
            "https://api.twitter.com/2/oauth2/token",
            auth=(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET),
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        token_data = resp.json()
        if "error" in token_data:
            return _redirect_error(_("error.oauth-token-exchange-failed").format(detail=token_data.get('error_description', token_data['error'])))
    except requests.RequestException as e:
        return _redirect_error(_("error.oauth-token-exchange-failed-detail").format(detail=e))

    access_token = token_data.get("access_token", "")
    token_data.get("refresh_token", "")

    # Get user info
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        info_resp = requests.get("https://api.twitter.com/2/users/me", headers=headers, timeout=10)
        info_data = info_resp.json()
        username = info_data.get("data", {}).get("username", "X Account")
        twitter_id = info_data.get("data", {}).get("id", "")
    except requests.RequestException:
        username = "X Account"
        twitter_id = ""

    existing = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user_id, SocialAccount.platform == "twitter").first()
    )
    if existing:
        existing.twitter_access_token_enc = encrypt_token(access_token)
        existing.twitter_user_id = twitter_id
        existing.account_name = username
    else:
        account = SocialAccount(
            user_id=user_id,
            platform="twitter",
            account_name=username,
            auth_mode="oauth",
            twitter_access_token_enc=encrypt_token(access_token),
            twitter_user_id=twitter_id,
        )
        db.add(account)
    db.commit()

    return _redirect_success("twitter")


# ── Facebook OAuth ────────────────────────────────────────────


@router.get("/facebook/authorize")
def facebook_authorize(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.FACEBOOK_CLIENT_ID or not settings.FACEBOOK_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail=_("error.facebook-not-configured"),
        )
    state = _generate_state(user.id, "facebook", db)
    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/facebook/callback"
    params = urllib.parse.urlencode(
        {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "pages_manage_posts,pages_read_engagement,pages_show_list",
            "response_type": "code",
            "state": state,
        }
    )
    return {"url": f"https://www.facebook.com/v22.0/dialog/oauth?{params}", "state": state}


@router.get("/facebook/callback")
def facebook_callback(
    code: str = Query(""), state: str = Query(""), error: str = Query(None), db: Session = Depends(get_db)
):
    if error:
        return _redirect_error(_("error.oauth-facebook-cancelled").format(error=error))
    data = _consume_state(state, db)
    user_id = data["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect_error(_("error.user-not-found"))

    import requests

    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/facebook/callback"

    try:
        resp = requests.post(
            "https://graph.facebook.com/v22.0/oauth/access_token",
            data={
                "client_id": settings.FACEBOOK_CLIENT_ID,
                "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        token_data = resp.json()
        if "error" in token_data:
            return _redirect_error(_("error.oauth-token-exchange-failed").format(detail=token_data.get('error', {}).get('message', str(token_data))))
    except requests.RequestException as e:
        return _redirect_error(_("error.oauth-token-exchange-failed-detail").format(detail=e))

    access_token = token_data.get("access_token", "")

    # Get Facebook pages
    page_id = ""
    page_name = "Facebook Page"
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        pages_resp = requests.get(
            "https://graph.facebook.com/v22.0/me/accounts?fields=id,name", headers=headers, timeout=10
        )
        pages_data = pages_resp.json()
        if "data" in pages_data and pages_data["data"]:
            page = pages_data["data"][0]
            page_id = page.get("id", "")
            page_name = page.get("name", "Facebook Page")
    except requests.RequestException:
        pass

    existing = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user_id, SocialAccount.platform == "facebook").first()
    )
    if existing:
        existing.facebook_access_token_enc = encrypt_token(access_token)
        existing.facebook_page_id = page_id
        existing.account_name = page_name
    else:
        account = SocialAccount(
            user_id=user_id,
            platform="facebook",
            account_name=page_name,
            auth_mode="oauth",
            facebook_access_token_enc=encrypt_token(access_token),
            facebook_page_id=page_id,
        )
        db.add(account)
    db.commit()

    return _redirect_success("facebook")


# ── LinkedIn OAuth ───────────────────────────────────────────


@router.get("/linkedin/authorize")
def linkedin_authorize(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail=_("error.linkedin-not-configured"),
        )
    state = _generate_state(user.id, "linkedin", db)
    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/linkedin/callback"
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email w_member_social",
            "state": state,
        }
    )
    return {"url": f"https://www.linkedin.com/oauth/v2/authorization?{params}", "state": state}


@router.get("/linkedin/callback")
def linkedin_callback(
    code: str = Query(""), state: str = Query(""), error: str = Query(None), db: Session = Depends(get_db)
):
    if error:
        return _redirect_error(_("error.oauth-linkedin-cancelled").format(error=error))
    data = _consume_state(state, db)
    user_id = data["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect_error(_("error.user-not-found"))

    import requests

    redirect_uri = f"{settings.PUBLIC_BASE_URL or 'http://localhost:8000'}/api/v1/oauth/linkedin/callback"

    try:
        resp = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        token_data = resp.json()
        if "error" in token_data:
            return _redirect_error(_("error.oauth-token-exchange-failed").format(detail=token_data.get('error_description', token_data['error'])))
    except requests.RequestException as e:
        return _redirect_error(_("error.oauth-token-exchange-failed-detail").format(detail=e))

    access_token = token_data.get("access_token", "")

    # Get LinkedIn user info
    user_name = "LinkedIn Account"
    linkedin_user_id = ""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        info_resp = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10)
        info_data = info_resp.json()
        user_name = info_data.get("name", "LinkedIn Account")
        linkedin_user_id = info_data.get("sub", "")
    except requests.RequestException:
        pass

    existing = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user_id, SocialAccount.platform == "linkedin").first()
    )
    if existing:
        existing.linkedin_access_token_enc = encrypt_token(access_token)
        existing.linkedin_user_id = linkedin_user_id
        existing.account_name = user_name
    else:
        account = SocialAccount(
            user_id=user_id,
            platform="linkedin",
            account_name=user_name,
            auth_mode="oauth",
            linkedin_access_token_enc=encrypt_token(access_token),
            linkedin_user_id=linkedin_user_id,
        )
        db.add(account)
    db.commit()

    return _redirect_success("linkedin")


# Cleanup stale states — called periodically from main startup
def cleanup_stale_states():
    from ...core.database import SessionLocal

    db = SessionLocal()
    try:
        cutoff = datetime.now(UTC) - timedelta(minutes=15)
        db.query(OAuthState).filter(OAuthState.created_at < cutoff).delete()
        db.commit()
    finally:
        db.close()
