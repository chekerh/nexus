"""Scheduler service — auto-publishes posts when their scheduled_at time arrives.

A background thread polls the database every 60 seconds for posts with
status='scheduled' and scheduled_at <= now, then attempts to publish them
through the existing publish pipeline.
"""

import logging
import os
import threading
import time
from datetime import UTC, datetime

from ..core.database import SessionLocal
from ..core.publisher import publish_clip
from ..core.security import decrypt_token
from ..models.account import SocialAccount
from ..models.persona import Post

logger = logging.getLogger("nexus.scheduler")


def _decrypt_account_tokens(account: SocialAccount) -> dict:
    return {
        "id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
        "youtube_privacy_status": account.youtube_privacy_status,
        "oauth_refresh_token": decrypt_token(account.oauth_refresh_token_enc),
        "instagram_user_id": account.instagram_user_id,
        "instagram_access_token": decrypt_token(account.instagram_access_token_enc),
        "tiktok_open_id": account.tiktok_open_id,
        "tiktok_refresh_token": decrypt_token(account.tiktok_refresh_token_enc),
        "tiktok_access_token": decrypt_token(account.tiktok_access_token_enc),
        "twitter_user_id": account.twitter_user_id,
        "twitter_access_token": decrypt_token(account.twitter_access_token_enc),
        "facebook_page_id": account.facebook_page_id,
        "facebook_access_token": decrypt_token(account.facebook_access_token_enc),
        "linkedin_user_id": account.linkedin_user_id,
        "linkedin_access_token": decrypt_token(account.linkedin_access_token_enc),
    }


def publish_scheduled_post(post: Post, db: SessionLocal) -> None:
    account = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == post.user_id,
            SocialAccount.platform == post.platform,
            SocialAccount.is_active,
        )
        .first()
    )
    if not account:
        post.status = "failed"
        post.error = "No active account for platform"
        db.commit()
        return

    clip_path = post.media_path
    if not clip_path or not os.path.exists(clip_path):
        post.status = "failed"
        post.error = "Media file not found"
        db.commit()
        return

    account_dict = _decrypt_account_tokens(account)
    try:
        publish_clip(
            platform=post.platform,
            account=account_dict,
            video_path=clip_path,
            title=post.title or "Nexus-UGC Post",
            description=post.body or "",
        )
        post.status = "posted"
        post.posted_at = datetime.now(UTC)
        post.error = None
        logger.info("Published scheduled post %s to %s", post.id, post.platform)
    except Exception as exc:
        post.status = "failed"
        post.error = str(exc)[:500]
        logger.warning("Scheduled post %s failed: %s", post.id, exc)
    db.commit()


class PostScheduler:
    def __init__(self):
        self._worker: threading.Thread | None = None
        self._running = False

    def start(self):
        if self._worker is not None:
            return
        self._running = True
        self._worker = threading.Thread(target=self._poll_loop, daemon=True, name="scheduler")
        self._worker.start()
        logger.info("PostScheduler started (poll interval 60s)")

    def stop(self, timeout: float = 10):
        self._running = False
        if self._worker:
            self._worker.join(timeout=timeout)
            self._worker = None
        logger.info("PostScheduler stopped")

    def _poll_loop(self):
        while self._running:
            try:
                self._publish_due_posts()
            except Exception:
                logger.exception("Scheduler poll cycle failed")
            for _ in range(60):
                if not self._running:
                    return
                time.sleep(1)

    def _publish_due_posts(self):
        db = SessionLocal()
        try:
            now = datetime.now(UTC)
            due = db.query(Post).filter(Post.status == "scheduled", Post.scheduled_at <= now).limit(50).all()
            for post in due:
                publish_scheduled_post(post, db)
        finally:
            db.close()


post_scheduler = PostScheduler()
