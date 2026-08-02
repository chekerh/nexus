"""Publishing API — publish clips to social platforms."""

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...core.publisher import SUPPORTED_PLATFORMS, PublishHistoryStore, publish_clip
from ...core.security import decrypt_token
from ...models.account import SocialAccount
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(tags=["publish"])

publish_history_store = PublishHistoryStore()


def _get_account_for_platform(db: Session, user_id: str, platform: str) -> SocialAccount | None:
    """Find the first active account for a platform belonging to the user."""
    return (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == platform,
            SocialAccount.is_active,
        )
        .first()
    )


def _get_account_token_dict(account: SocialAccount) -> dict:
    """Extract a unified token dict from an account, regardless of platform."""
    tokens = {"id": account.id, "platform": account.platform}
    if account.oauth_refresh_token_enc:
        tokens["refresh_token"] = decrypt_token(account.oauth_refresh_token_enc)
    if account.instagram_access_token_enc:
        tokens["access_token"] = decrypt_token(account.instagram_access_token_enc)
    if account.instagram_user_id:
        tokens["page_id"] = account.instagram_user_id
        tokens["person_id"] = account.instagram_user_id
    if account.tiktok_access_token_enc:
        tokens["access_token"] = decrypt_token(account.tiktok_access_token_enc)
    if account.tiktok_refresh_token_enc:
        tokens["refresh_token"] = decrypt_token(account.tiktok_refresh_token_enc)
    if account.tiktok_open_id:
        tokens["open_id"] = account.tiktok_open_id
    if account.twitter_user_id:
        tokens["twitter_user_id"] = account.twitter_user_id
    if account.twitter_access_token_enc:
        tokens["access_token"] = decrypt_token(account.twitter_access_token_enc)
    if account.facebook_page_id:
        tokens["page_id"] = account.facebook_page_id
    if account.facebook_access_token_enc:
        tokens["access_token"] = decrypt_token(account.facebook_access_token_enc)
    if account.linkedin_user_id:
        tokens["person_id"] = account.linkedin_user_id
    if account.linkedin_access_token_enc:
        tokens["access_token"] = decrypt_token(account.linkedin_access_token_enc)
    return tokens


class PublishRequest(BaseModel):
    platform: str
    account_id: str
    clip_filename: str
    title: str
    description: str = ""


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


@router.post("/publish")
def publish_to_social(
    payload: PublishRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=_("error.unsupported-platform"))

    safe_clip = os.path.basename(payload.clip_filename)
    if (
        not payload.clip_filename
        or safe_clip != payload.clip_filename
        or ".." in payload.clip_filename
        or payload.clip_filename.startswith(("/", "\\"))
    ):
        raise HTTPException(status_code=400, detail=_("error.invalid-clip-filename"))

    account = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.id == payload.account_id,
            SocialAccount.user_id == user.id,
            SocialAccount.is_active,
        )
        .first()
    )

    if not account:
        raise HTTPException(status_code=404, detail=_("error.account-not-found"))
    if account.platform != payload.platform:
        raise HTTPException(status_code=400, detail=_("error.account-platform-mismatch"))

    clip_path = os.path.join(settings.UPLOAD_DIR, "clips", safe_clip)
    if not os.path.exists(clip_path):
        raise HTTPException(status_code=404, detail=_("error.clip-not-found"))

    account_dict = _decrypt_account_tokens(account)
    result = publish_clip(
        platform=payload.platform,
        account=account_dict,
        video_path=clip_path,
        title=payload.title.strip(),
        description=payload.description.strip(),
    )

    row = {
        "user_id": user.id,
        "platform": payload.platform,
        "account_id": account.id,
        "account_name": account.account_name,
        "clip_filename": payload.clip_filename,
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "result": result,
        "created_at": datetime.now(UTC).isoformat(),
    }
    publish_history_store.append(db, row)

    return {"publish": row}


@router.get("/publish/history")
def get_publish_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"history": publish_history_store.list(db, user.id)}
