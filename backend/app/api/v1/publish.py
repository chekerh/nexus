"""Publishing API — publish clips to social platforms."""
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.config import settings
from ...core.security import decrypt_token
from ...core.publisher import publish_clip, PublishHistoryStore, SUPPORTED_PLATFORMS
from ...models.user import User
from ...models.account import SocialAccount
from ...core.publisher import MANUAL_UPLOAD_URL
from ..deps import get_current_user

router = APIRouter(tags=["publish"])

publish_history_store = PublishHistoryStore(settings.PUBLISH_LOG_PATH)


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
    }


@router.post("/publish")
def publish_to_social(
    payload: PublishRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    account = db.query(SocialAccount).filter(
        SocialAccount.id == payload.account_id,
        SocialAccount.user_id == user.id,
        SocialAccount.is_active == True,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.platform != payload.platform:
        raise HTTPException(status_code=400, detail="Account/platform mismatch")

    clip_path = os.path.join(settings.UPLOAD_DIR, "clips", payload.clip_filename)
    if not os.path.exists(clip_path):
        raise HTTPException(status_code=404, detail="Clip not found")

    account_dict = _decrypt_account_tokens(account)
    result = publish_clip(
        platform=payload.platform,
        account=account_dict,
        video_path=clip_path,
        title=payload.title.strip(),
        description=payload.description.strip(),
    )

    row = {
        "platform": payload.platform,
        "account_id": account.id,
        "account_name": account.account_name,
        "clip_filename": payload.clip_filename,
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "result": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    publish_history_store.append(row)

    return {"publish": row}


@router.get("/publish/history")
def get_publish_history(user: User = Depends(get_current_user)):
    return {"history": publish_history_store.list()}
