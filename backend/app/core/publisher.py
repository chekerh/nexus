import json
import os
import time
from datetime import datetime, UTC
from typing import Dict, List
import httpx
from urllib.parse import quote
from .config import settings

SUPPORTED_PLATFORMS = ["tiktok", "instagram", "youtube"]

MANUAL_UPLOAD_URL = {
    "tiktok": "https://www.tiktok.com/upload",
    "instagram": "https://www.instagram.com/create/select/",
    "youtube": "https://studio.youtube.com",
}


class PublishHistoryStore:
    def __init__(self, file_path: str):
        self.file_path = file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def list(self) -> List[Dict]:
        with open(self.file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def append(self, row: Dict) -> Dict:
        rows = self.list()
        rows.append(row)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
        return row


def publish_clip(platform: str, account: Dict, video_path: str, title: str, description: str) -> Dict:
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

    if platform == "youtube":
        youtube_result = _publish_to_youtube(account, video_path, title, description)
        if youtube_result.get("status") == "published":
            youtube_result.update({
                "platform": platform,
                "account_name": account_name,
                "created_at": datetime.now(UTC).isoformat(),
            })
            return youtube_result

    if platform == "instagram":
        instagram_result = _publish_to_instagram(account, video_path, title, description)
        if instagram_result.get("status") == "published":
            instagram_result.update({
                "platform": platform,
                "account_name": account_name,
                "created_at": datetime.now(UTC).isoformat(),
            })
            return instagram_result

    return {
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
    }


def _publish_to_instagram(account: Dict, video_path: str, title: str, description: str) -> Dict:
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


def _publish_to_youtube(account: Dict, video_path: str, title: str, description: str) -> Dict:
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
