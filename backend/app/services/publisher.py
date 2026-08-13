"""Auto-publish worker — checks scheduled posts and publishes them on time.

Runs as a background thread in the FastAPI app. Checks every 60s for posts
whose scheduled_at has passed and publishes them via the appropriate platform API.
"""

import logging
import os
import threading
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.security import decrypt_token
from ..models.persona import Post

logger = logging.getLogger("nexus.publisher")


def _publish_to_platform(post: Post, db: Session) -> tuple[bool, str]:
    """Publish a post to its target platform.

    Returns (success: bool, error_message: str).
    """

    platform = post.platform

    try:
        if platform == "youtube":
            return _publish_youtube(post, db)
        elif platform == "tiktok":
            return _publish_tiktok(post, db)
        elif platform in ("instagram", "facebook"):
            return _publish_meta(post, db, platform)
        elif platform == "twitter":
            return _publish_twitter(post, db)
        elif platform == "linkedin":
            return _publish_linkedin(post, db)
        else:
            return False, f"Unknown platform: {platform}"
    except Exception as e:
        return False, str(e)


def _publish_youtube(post: Post, db: Session) -> tuple[bool, str]:
    """Publish to YouTube via core publisher."""
    from ..api.v1.publish import _get_account_for_platform

    account = _get_account_for_platform(db, post.user_id, "youtube")
    if not account:
        return False, "No YouTube account connected"

    refresh_token = decrypt_token(account.oauth_refresh_token_enc) if account.oauth_refresh_token_enc else ""
    if not refresh_token:
        return False, "No YouTube refresh token — reconnect account"

    account_dict = {
        "oauth_refresh_token": refresh_token,
        "youtube_privacy_status": account.youtube_privacy_status or "private",
    }

    from ..core.publisher import _publish_to_youtube

    title = post.title or "Nexus-UGC Video"
    description = post.body or "Created with Nexus-UGC"

    result = _publish_to_youtube(account_dict, post.media_path, title, description)
    if result.get("status") == "published":
        return True, ""
    return False, result.get("reason", result.get("message", "Unknown error"))


def _publish_tiktok(post: Post, db: Session) -> tuple[bool, str]:
    """Publish to TikTok via core publisher."""
    from ..api.v1.publish import _get_account_for_platform

    account = _get_account_for_platform(db, post.user_id, "tiktok")
    if not account:
        return False, "No TikTok account connected"

    access_token = decrypt_token(account.tiktok_access_token_enc) if account.tiktok_access_token_enc else ""
    refresh_token = decrypt_token(account.tiktok_refresh_token_enc) if account.tiktok_refresh_token_enc else ""

    account_dict = {
        "tiktok_access_token": access_token,
        "tiktok_refresh_token": refresh_token,
    }

    from ..core.publisher import _publish_to_tiktok

    title = post.title or "Nexus-UGC Video"
    description = post.body or "Created with Nexus-UGC"

    result = _publish_to_tiktok(account_dict, post.media_path, title, description)
    if result.get("status") in ("published", "submitted"):
        return True, ""
    return False, result.get("reason", result.get("message", "Unknown error"))


def _publish_meta(post: Post, db: Session, platform: str) -> tuple[bool, str]:
    """Publish to Instagram or Facebook via Graph API."""
    from ..api.v1.publish import _get_account_for_platform

    account = _get_account_for_platform(db, post.user_id, platform)
    if not account:
        return False, f"No {platform} account connected"

    access_token = decrypt_token(account.instagram_access_token_enc) if account.instagram_access_token_enc else ""
    page_id = account.instagram_user_id or ""

    try:
        import requests

        if platform == "instagram":
            url = f"https://graph.facebook.com/v22.0/{page_id}/media"
            caption = post.body or "Created with Nexus-UGC"
            if post.media_path:
                # Image post
                import mimetypes

                mime = mimetypes.guess_type(post.media_path)[0] or "image/jpeg"
                if mime.startswith("video"):
                    params = {
                        "media_type": "VIDEO",
                        "video_url": post.media_path,
                        "caption": caption,
                        "access_token": access_token,
                    }
                else:
                    params = {
                        "image_url": post.media_path,
                        "caption": caption,
                        "access_token": access_token,
                    }
                resp = requests.post(url, data=params, timeout=30)
                data = resp.json()
                if "id" in data:
                    # Publish
                    creation_id = data["id"]
                    publish_url = f"https://graph.facebook.com/v22.0/{page_id}/media_publish"
                    pub_resp = requests.post(
                        publish_url,
                        data={
                            "creation_id": creation_id,
                            "access_token": access_token,
                        },
                        timeout=30,
                    )
                    if pub_resp.status_code == 200:
                        return True, ""
                    return False, pub_resp.text[:500]
                return False, data.get("error", {}).get("message", str(data))[:500]

            # Text-only post
            url = f"https://graph.facebook.com/v22.0/{page_id}/feed"
            resp = requests.post(
                url,
                data={
                    "message": post.body,
                    "access_token": access_token,
                },
                timeout=30,
            )
            return resp.status_code == 200, resp.text[:500] if resp.status_code != 200 else ""
        else:
            # Facebook
            url = f"https://graph.facebook.com/v22.0/{page_id}/feed"
            params = {
                "message": post.body or "Created with Nexus-UGC",
                "access_token": access_token,
            }
            if post.media_path and os.path.exists(post.media_path):
                with open(post.media_path, "rb") as f:
                    files = {"source": f}
                    resp = requests.post(url, data=params, files=files, timeout=60)
                data = resp.json()
                if "id" in data:
                    return True, ""
                return False, data.get("error", {}).get("message", str(data))[:500]
            resp = requests.post(url, data=params, timeout=30)
            if "id" in resp.json():
                return True, ""
            return False, resp.text[:500]
    except Exception as e:
        return False, str(e)


def _publish_twitter(post: Post, db: Session) -> tuple[bool, str]:
    """Publish to X/Twitter via API v2."""
    from ..api.v1.publish import _get_account_for_platform
    from ..core.config import settings

    account = _get_account_for_platform(db, post.user_id, "twitter")
    if not account:
        return False, "No X/Twitter account connected"

    bearer = ""
    refresh = decrypt_token(account.oauth_refresh_token_enc) if account.oauth_refresh_token_enc else ""
    access_token = decrypt_token(account.twitter_access_token_enc) if account.twitter_access_token_enc else ""

    try:
        import requests

        # Try access token first, then refresh
        if access_token:
            bearer = access_token
        elif refresh:
            resp = requests.post(
                "https://api.twitter.com/2/oauth2/token",
                data={
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                    "client_id": settings.TWITTER_CLIENT_ID or os.getenv("TWITTER_CLIENT_ID", ""),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            if resp.status_code == 200:
                bearer = resp.json().get("access_token", bearer)

        headers = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
        text = post.body or ""

        if post.media_path and os.path.exists(post.media_path):
            # Upload media first
            upload_headers = {"Authorization": f"Bearer {bearer}"}
            with open(post.media_path, "rb") as f:
                upload_resp = requests.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers=upload_headers,
                    files={"media": f},
                    timeout=60,
                )
                if upload_resp.status_code == 200:
                    media_id = upload_resp.json().get("media_id_string")
                    if media_id:
                        payload = {"text": text, "media": {"media_ids": [media_id]}}
                        resp = requests.post(
                            "https://api.twitter.com/2/tweets", headers=headers, json=payload, timeout=30
                        )
                        return resp.status_code == 201, resp.text[:500] if resp.status_code != 201 else ""

            # Fallback: post text only
            resp = requests.post("https://api.twitter.com/2/tweets", headers=headers, json={"text": text}, timeout=30)
            return resp.status_code == 201, resp.text[:500] if resp.status_code != 201 else ""

        resp = requests.post("https://api.twitter.com/2/tweets", headers=headers, json={"text": text}, timeout=30)
        return resp.status_code == 201, resp.text[:500] if resp.status_code != 201 else ""
    except Exception as e:
        return False, str(e)


def _publish_linkedin(post: Post, db: Session) -> tuple[bool, str]:
    """Publish to LinkedIn."""
    from ..api.v1.publish import _get_account_for_platform

    account = _get_account_for_platform(db, post.user_id, "linkedin")
    if not account:
        return False, "No LinkedIn account connected"

    access_token = decrypt_token(account.oauth_refresh_token_enc) if account.oauth_refresh_token_enc else ""
    person_id = account.linkedin_user_id or "me"

    try:
        import requests

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        text = post.body or "Created with Nexus-UGC"

        if post.media_path and os.path.exists(post.media_path):
            # Register upload first
            register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
            register_payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:person:{person_id}" if person_id != "me" else "urn:li:person:me",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent",
                        }
                    ],
                }
            }
            reg_resp = requests.post(register_url, headers=headers, json=register_payload, timeout=15)
            if reg_resp.status_code == 200:
                reg_data = reg_resp.json()
                upload_url = (
                    reg_data.get("value", {})
                    .get("uploadMechanism", {})
                    .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
                    .get("uploadUrl", "")
                )
                asset = reg_data.get("value", {}).get("asset", "")

                if upload_url and asset:
                    with open(post.media_path, "rb") as f:
                        requests.put(upload_url, data=f, timeout=60)

                    # Create post with image
                    post_payload = {
                        "author": f"urn:li:person:{person_id}" if person_id != "me" else "urn:li:person:me",
                        "lifecycleState": "PUBLISHED",
                        "specificContent": {
                            "com.linkedin.ugc.ShareContent": {
                                "shareCommentary": {"text": text},
                                "shareMediaCategory": "IMAGE",
                                "media": [
                                    {
                                        "status": "READY",
                                        "description": {"text": post.title or ""},
                                        "media": asset,
                                        "title": {"text": post.title or ""},
                                    }
                                ],
                            }
                        },
                        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                    }
                    post_resp = requests.post(
                        "https://api.linkedin.com/v2/ugcPosts", headers=headers, json=post_payload, timeout=30
                    )
                    return post_resp.status_code == 201, post_resp.text[:500] if post_resp.status_code != 201 else ""

        # Text-only post
        post_payload = {
            "author": f"urn:li:person:{person_id}" if person_id != "me" else "urn:li:person:me",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = requests.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=post_payload, timeout=30)
        return resp.status_code == 201, resp.text[:500] if resp.status_code != 201 else ""
    except Exception as e:
        return False, str(e)


def _process_scheduled_posts():
    """Find and publish all scheduled posts whose time has come, plus auto-post approved content."""
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        # Scheduled posts whose publish time has arrived
        due_posts = (
            db.query(Post)
            .filter(
                Post.status == "scheduled",
                Post.scheduled_at <= now,
            )
            .limit(20)
            .all()
        )

        # Approved posts that should be published immediately (auto-approve flow)
        approved_posts = (
            db.query(Post)
            .filter(
                Post.status == "approved",
            )
            .limit(10)
            .all()
        )

        all_due = due_posts + approved_posts

        for post in all_due:
            logger.info(f"Auto-publishing post {post.id} to {post.platform}")
            success, error = _publish_to_platform(post, db)
            if success:
                post.status = "posted"
                post.posted_at = datetime.now(UTC)
                post.error = ""
            else:
                post.status = "failed"
                post.error = error[:500]
                logger.error(f"Failed to publish post {post.id}: {error}")

        db.commit()
    except Exception as e:
        logger.error(f"Error in publish worker: {e}")
    finally:
        db.close()


def start_publish_worker():
    """Start the background auto-publish worker thread."""

    def worker_loop():
        logger.info("Auto-publish worker started (60s interval)")
        while True:
            try:
                _process_scheduled_posts()
            except Exception as e:
                logger.error(f"Publish worker error: {e}")
            time.sleep(60)

    thread = threading.Thread(target=worker_loop, daemon=True, name="publish-worker")
    thread.start()
    return thread
