import builtins
import os
import time
import json
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from .config import settings

SUPPORTED_PLATFORMS = ["tiktok", "instagram", "youtube", "twitter", "facebook", "linkedin"]

MANUAL_UPLOAD_URL = {
    "tiktok": "https://www.tiktok.com/upload",
    "instagram": "https://www.instagram.com/create/select/",
    "youtube": "https://studio.youtube.com",
    "twitter": "https://twitter.com/compose/tweet",
    "facebook": "https://www.facebook.com/upload",
    "linkedin": "https://www.linkedin.com/post/new",
}


def _attach_result_url(result: dict) -> dict:
    if not isinstance(result, dict):
        return result
    if result.get("result_url"):
        return result
    url = result.get("video_url") or result.get("mock_url") or result.get("upload_url")
    if url:
        result["result_url"] = url
    return result


class PublishHistoryStore:
    def list(self, db: Session, user_id: int) -> builtins.list[dict]:
        from ..models.publish_history import PublishHistory

        rows = (
            db.query(PublishHistory)
            .filter(PublishHistory.user_id == user_id)
            .order_by(PublishHistory.created_at.desc())
            .all()
        )
        return [
            {
                "platform": r.platform,
                "account_id": r.account_id,
                "account_name": r.account_name,
                "clip_filename": r.clip_filename,
                "title": r.title,
                "description": r.description,
                "result": r.result,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def append(self, db: Session, row: dict) -> dict:
        from ..models.publish_history import PublishHistory

        record = PublishHistory(
            user_id=row["user_id"],
            platform=row["platform"],
            account_id=row.get("account_id"),
            account_name=row.get("account_name"),
            clip_filename=row.get("clip_filename"),
            title=row.get("title"),
            description=row.get("description"),
            result=row.get("result"),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        row["id"] = record.id
        return row


def publish_clip(platform: str, account: dict, video_path: str, title: str, description: str) -> dict:
    """
    Publishing orchestrator.

    NOTE:
    - We keep this safe and API-compliant by defaulting to manual upload links.
    - Official direct posting for TikTok/Instagram/YouTube requires app approval,
      OAuth scopes, and/or publicly reachable media URLs.
    """
    platform = platform.lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        return {
            "status": "error",
            "error": f"Unsupported platform: {platform}",
        }

    account_name = account.get("account_name", "Unknown account")

    # Dev-mode deterministic publish for local testing
    if os.getenv("DEV_PUBLISH_MOCK", "").lower() in ("1", "true", "yes"):
        try:
            result = _dev_publish(platform, account, video_path, title, description)
            result.update(
                {
                    "platform": platform,
                    "account_name": account_name,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            return _attach_result_url(result)
        except Exception:
            # fall through to normal behavior on failure
            pass

    if platform == "youtube":
        youtube_result = _publish_to_youtube(account, video_path, title, description)
        if youtube_result.get("status") == "published":
            youtube_result.update(
                {
                    "platform": platform,
                    "account_name": account_name,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            return _attach_result_url(youtube_result)

    if platform == "instagram":
        instagram_result = _publish_to_instagram(account, video_path, title, description)
        if instagram_result.get("status") == "published":
            instagram_result.update(
                {
                    "platform": platform,
                    "account_name": account_name,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            return _attach_result_url(instagram_result)

    if platform == "tiktok":
        tiktok_result = _publish_to_tiktok(account, video_path, title, description)
        if tiktok_result.get("status") in {"published", "submitted"}:
            tiktok_result.update(
                {
                    "platform": platform,
                    "account_name": account_name,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            return _attach_result_url(tiktok_result)

    return _attach_result_url({
        "status": "manual_required",
        "platform": platform,
        "account_name": account_name,
        "upload_url": MANUAL_UPLOAD_URL.get(platform),
        "title": title,
        "description": description,
        "video_path": video_path,
        "message": (
            "Official auto-publish needs platform app credentials and approval. "
            "Open upload URL while logged into the selected account and upload this generated clip."
        ),
        "created_at": datetime.now(UTC).isoformat(),
    })


def _dev_publish(platform: str, account: dict, video_path: str, title: str, description: str) -> dict:
    """Write a deterministic publish record to the PUBLISH_LOG_PATH and return a 'published' result.

    This is intended for local tests and CI where real platform credentials are not available.
    Enable via `DEV_PUBLISH_MOCK=true` in the environment.
    """
    entry = {
        "platform": platform,
        "account": account.get("account_name") or account.get("id") or "dev",
        "video_path": video_path,
        "title": title,
        "description": description,
        "status": "published",
        "mock_url": f"http://{(settings.PUBLIC_BASE_URL or 'localhost').lstrip('http://').lstrip('https://')}/mock/{int(time.time())}",
        "created_at": datetime.now(UTC).isoformat(),
    }

    log_path = settings.PUBLISH_LOG_PATH
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        # append as JSON lines for easy consumption
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # ignore logging errors in dev mock
        pass

    return {
        "status": "published",
        "video_url": entry["mock_url"],
        "mock_url": entry["mock_url"],
        "result_url": entry["mock_url"],
        "message": "Dev-mode mock published",
    }


def _publish_to_tiktok(account: dict, video_path: str, title: str, description: str) -> dict:
    api_base = settings.TIKTOK_API_BASE.strip().rstrip("/")
    client_key = settings.TIKTOK_CLIENT_KEY.strip()
    client_secret = settings.TIKTOK_CLIENT_SECRET.strip()
    public_base = settings.PUBLIC_BASE_URL.strip().rstrip("/")

    if not client_key or not client_secret:
        return {
            "status": "manual_required",
            "reason": "Missing TIKTOK_CLIENT_KEY/TIKTOK_CLIENT_SECRET",
            "upload_url": MANUAL_UPLOAD_URL["tiktok"],
            "message": "Set TikTok app credentials in .env for direct publishing.",
        }

    if not public_base:
        return {
            "status": "manual_required",
            "reason": "Missing PUBLIC_BASE_URL",
            "upload_url": MANUAL_UPLOAD_URL["tiktok"],
            "message": "Set PUBLIC_BASE_URL to a publicly reachable URL so TikTok can fetch media.",
        }

    access_token = (account.get("tiktok_access_token") or "").strip()
    refresh_token = (account.get("tiktok_refresh_token") or "").strip()

    if not access_token and refresh_token:
        access_token = _tiktok_refresh_access_token(api_base, client_key, client_secret, refresh_token)

    if not access_token:
        return {
            "status": "manual_required",
            "reason": "Missing or invalid TikTok access/refresh token",
            "upload_url": MANUAL_UPLOAD_URL["tiktok"],
            "message": "Reconnect TikTok account to enable direct publish.",
        }

    clip_name = quote(os.path.basename(video_path))
    video_url = f"{public_base}/video_clips/{clip_name}"
    post_title = (title or "").strip()[:150]
    post_desc = (description or "").strip()[:2200]
    final_caption = (post_title + "\n\n" + post_desc).strip()[:2200]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "post_info": {
            "title": post_title,
            "description": final_caption,
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{api_base}/v2/post/publish/video/init/", headers=headers, json=body)
        if resp.status_code not in (200, 201):
            return {
                "status": "manual_required",
                "reason": f"TikTok publish init failed ({resp.status_code}): {resp.text}",
                "upload_url": MANUAL_UPLOAD_URL["tiktok"],
                "message": "Fallback to manual upload.",
            }

        data = resp.json()
        publish_id = data.get("data", {}).get("publish_id", "") or data.get("publish_id", "")

        if not publish_id:
            return {
                "status": "submitted",
                "message": "TikTok init accepted but publish ID not returned. Check TikTok inbox/drafts.",
            }

        return {
            "status": "submitted",
            "publish_id": publish_id,
            "message": "TikTok post submitted. Check TikTok app/account for processing completion.",
        }


def _tiktok_refresh_access_token(api_base: str, client_key: str, client_secret: str, refresh_token: str) -> str:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{api_base}/v2/oauth/token/",
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        return data.get("access_token", "") or data.get("data", {}).get("access_token", "")


def _publish_to_instagram(account: dict, video_path: str, title: str, description: str) -> dict:
    user_id = (account.get("instagram_user_id") or "").strip()
    access_token = (account.get("instagram_access_token") or "").strip()
    public_base = settings.PUBLIC_BASE_URL.strip().rstrip("/")
    if not user_id or not access_token:
        return {
            "status": "manual_required",
            "reason": "Missing instagram_user_id or instagram_access_token",
            "upload_url": MANUAL_UPLOAD_URL["instagram"],
            "message": "Add Instagram Business account credentials to enable direct publish.",
        }

    if not public_base:
        return {
            "status": "manual_required",
            "reason": "Missing PUBLIC_BASE_URL",
            "upload_url": MANUAL_UPLOAD_URL["instagram"],
            "message": "Set PUBLIC_BASE_URL to a publicly reachable URL so Instagram can fetch clip media.",
        }

    clip_name = quote(os.path.basename(video_path))
    video_url = f"{public_base}/video_clips/{clip_name}"
    caption = f"{title}\n\n{description}".strip()
    graph = f"https://graph.facebook.com/{settings.INSTAGRAM_GRAPH_VERSION}"

    with httpx.Client(timeout=60) as client:
        create_resp = client.post(
            f"{graph}/{user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "access_token": access_token,
            },
        )
        if create_resp.status_code not in (200, 201):
            return {
                "status": "manual_required",
                "reason": f"Instagram container create failed ({create_resp.status_code}): {create_resp.text}",
                "upload_url": MANUAL_UPLOAD_URL["instagram"],
                "message": "Fallback to manual upload.",
            }

        creation_id = create_resp.json().get("id", "")
        if not creation_id:
            return {
                "status": "manual_required",
                "reason": "Instagram did not return creation container ID",
                "upload_url": MANUAL_UPLOAD_URL["instagram"],
                "message": "Fallback to manual upload.",
            }

        status = _wait_instagram_container_ready(client, graph, creation_id, access_token)
        if status not in {"FINISHED", "PUBLISHED"}:
            return {
                "status": "manual_required",
                "reason": f"Instagram media container not ready: {status}",
                "upload_url": MANUAL_UPLOAD_URL["instagram"],
                "message": "Fallback to manual upload.",
            }

        publish_resp = client.post(
            f"{graph}/{user_id}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": access_token,
            },
        )
        if publish_resp.status_code not in (200, 201):
            return {
                "status": "manual_required",
                "reason": f"Instagram publish failed ({publish_resp.status_code}): {publish_resp.text}",
                "upload_url": MANUAL_UPLOAD_URL["instagram"],
                "message": "Fallback to manual upload.",
            }

        media_id = publish_resp.json().get("id", "")
        return {
            "status": "published",
            "media_id": media_id,
            "video_url": f"https://www.instagram.com/reel/{media_id}/" if media_id else None,
            "message": "Reel published to Instagram successfully.",
        }


def _wait_instagram_container_ready(client: httpx.Client, graph_base: str, creation_id: str, access_token: str) -> str:
    # Small bounded polling loop.
    for _ in range(10):
        resp = client.get(
            f"{graph_base}/{creation_id}",
            params={
                "fields": "status_code",
                "access_token": access_token,
            },
        )
        if resp.status_code != 200:
            return "ERROR"
        status = (resp.json().get("status_code") or "").upper()
        if status in {"FINISHED", "PUBLISHED", "ERROR", "EXPIRED"}:
            return status
        time.sleep(2)
    return "TIMEOUT"


def _publish_to_youtube(account: dict, video_path: str, title: str, description: str) -> dict:
    refresh_token = (account.get("oauth_refresh_token") or "").strip()
    if not refresh_token:
        return {
            "status": "manual_required",
            "reason": "Missing account refresh token",
            "upload_url": MANUAL_UPLOAD_URL["youtube"],
            "message": "Add a YouTube account with refresh token to enable direct publish.",
        }

    client_id = settings.YOUTUBE_CLIENT_ID.strip()
    client_secret = settings.YOUTUBE_CLIENT_SECRET.strip()
    if not client_id or not client_secret:
        return {
            "status": "manual_required",
            "reason": "Missing YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET in .env",
            "upload_url": MANUAL_UPLOAD_URL["youtube"],
            "message": "Set YouTube OAuth client in .env to enable direct publish.",
        }

    token = _youtube_access_token(client_id, client_secret, refresh_token)
    if not token:
        return {
            "status": "manual_required",
            "reason": "Failed to exchange refresh token",
            "upload_url": MANUAL_UPLOAD_URL["youtube"],
            "message": "Refresh token invalid/expired, reconnect account.",
        }

    privacy_status = (account.get("youtube_privacy_status") or "private").strip().lower()
    if privacy_status not in {"private", "unlisted", "public"}:
        privacy_status = "private"

    try:
        video_id = _youtube_upload_video(
            access_token=token,
            video_path=video_path,
            title=title,
            description=description,
            privacy_status=privacy_status,
        )
        if not video_id:
            raise RuntimeError("Upload completed but no video ID returned.")

        return {
            "status": "published",
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "privacy_status": privacy_status,
            "message": "Video published to YouTube successfully.",
        }
    except Exception as e:
        return {
            "status": "manual_required",
            "reason": f"YouTube upload failed: {e}",
            "upload_url": MANUAL_UPLOAD_URL["youtube"],
            "message": "Fallback to manual upload in YouTube Studio.",
        }


def _youtube_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=30) as client:
        response = client.post("https://oauth2.googleapis.com/token", data=payload)
        if response.status_code != 200:
            return ""
        data = response.json()
        return data.get("access_token", "")


def _youtube_upload_video(access_token: str, video_path: str, title: str, description: str, privacy_status: str) -> str:
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?part=snippet,status&uploadType=resumable"
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    file_size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(file_size),
    }

    with httpx.Client(timeout=None) as client:
        init_resp = client.post(init_url, headers=headers, json=metadata)
        if init_resp.status_code not in (200, 201):
            raise RuntimeError(f"Init upload failed ({init_resp.status_code}): {init_resp.text}")

        upload_url = init_resp.headers.get("Location", "")
        if not upload_url:
            raise RuntimeError("No resumable upload URL returned by YouTube API.")

        with open(video_path, "rb") as f:
            upload_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
            }
            upload_resp = client.put(upload_url, headers=upload_headers, content=f.read())

        if upload_resp.status_code not in (200, 201):
            raise RuntimeError(f"Upload failed ({upload_resp.status_code}): {upload_resp.text}")

        body = upload_resp.json()
        return body.get("id", "")
