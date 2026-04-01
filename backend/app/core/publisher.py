import json
import os
from datetime import datetime, UTC
from typing import Dict, List

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
