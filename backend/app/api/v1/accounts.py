"""Social media accounts and groups API."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.i18n import _
from ...core.security import encrypt_token
from ...models.account import AccountGroup, GroupAccount, SocialAccount
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(tags=["accounts"])

SUPPORTED_PLATFORMS = ["tiktok", "instagram", "youtube", "twitter", "facebook", "linkedin"]


class AccountCreate(BaseModel):
    platform: str
    account_name: str
    auth_mode: str = "manual"
    notes: str = ""
    oauth_refresh_token: str = ""
    youtube_privacy_status: str = "private"
    instagram_user_id: str = ""
    instagram_access_token: str = ""
    tiktok_open_id: str = ""
    tiktok_refresh_token: str = ""
    tiktok_access_token: str = ""
    twitter_user_id: str = ""
    twitter_access_token: str = ""
    facebook_page_id: str = ""
    facebook_access_token: str = ""
    linkedin_user_id: str = ""
    linkedin_access_token: str = ""


class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


def _sanitize(account: SocialAccount) -> dict:
    return {
        "id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
        "auth_mode": account.auth_mode,
        "notes": account.notes,
        "youtube_privacy_status": account.youtube_privacy_status,
        "instagram_user_id": account.instagram_user_id,
        "tiktok_open_id": account.tiktok_open_id,
        "has_oauth_refresh_token": bool(account.oauth_refresh_token_enc),
        "has_instagram_access_token": bool(account.instagram_access_token_enc),
        "has_tiktok_refresh_token": bool(account.tiktok_refresh_token_enc),
        "has_tiktok_access_token": bool(account.tiktok_access_token_enc),
        "twitter_user_id": account.twitter_user_id,
        "has_twitter_access_token": bool(account.twitter_access_token_enc),
        "facebook_page_id": account.facebook_page_id,
        "has_facebook_access_token": bool(account.facebook_access_token_enc),
        "linkedin_user_id": account.linkedin_user_id,
        "has_linkedin_access_token": bool(account.linkedin_access_token_enc),
        "is_active": account.is_active,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


@router.get("/platforms")
def list_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


@router.get("/accounts")
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user.id, SocialAccount.is_active).limit(200).all()
    )
    return {"accounts": [_sanitize(a) for a in accounts]}


@router.post("/accounts")
def create_account(payload: AccountCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=_("error.unsupported-platform"))

    account = SocialAccount(
        user_id=user.id,
        platform=payload.platform,
        account_name=payload.account_name,
        auth_mode=payload.auth_mode,
        notes=payload.notes,
        oauth_refresh_token_enc=encrypt_token(payload.oauth_refresh_token),
        youtube_privacy_status=payload.youtube_privacy_status,
        instagram_user_id=payload.instagram_user_id,
        instagram_access_token_enc=encrypt_token(payload.instagram_access_token),
        tiktok_open_id=payload.tiktok_open_id,
        tiktok_refresh_token_enc=encrypt_token(payload.tiktok_refresh_token),
        tiktok_access_token_enc=encrypt_token(payload.tiktok_access_token),
        twitter_user_id=payload.twitter_user_id,
        twitter_access_token_enc=encrypt_token(payload.twitter_access_token),
        facebook_page_id=payload.facebook_page_id,
        facebook_access_token_enc=encrypt_token(payload.facebook_access_token),
        linkedin_user_id=payload.linkedin_user_id,
        linkedin_access_token_enc=encrypt_token(payload.linkedin_access_token),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"account": _sanitize(account)}


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id, SocialAccount.user_id == user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail=_("error.account-not-found"))
    account.is_active = False
    db.commit()
    return {"status": "deleted"}


@router.get("/account-groups")
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    groups = db.query(AccountGroup).filter(AccountGroup.user_id == user.id).limit(200).all()
    all_accounts = (
        db.query(SocialAccount).filter(SocialAccount.user_id == user.id, SocialAccount.is_active).limit(200).all()
    )
    account_map = {a.id: a for a in all_accounts}

    group_ids = [g.id for g in groups]
    mappings = db.query(GroupAccount).filter(GroupAccount.group_id.in_(group_ids)).limit(200).all()
    group_accounts: dict[str, list] = {}
    for m in mappings:
        group_accounts.setdefault(m.group_id, []).append(m)

    result = []
    for g in groups:
        accounts = []
        for m in group_accounts.get(g.id, []):
            if m.account_id in account_map:
                accounts.append(_sanitize(account_map[m.account_id]))
        result.append(
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "accounts": accounts,
            }
        )
    return {"groups": result}


@router.post("/account-groups")
def create_group(payload: GroupCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = AccountGroup(user_id=user.id, name=payload.name, description=payload.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"group": {"id": group.id, "name": group.name, "description": group.description, "accounts": []}}


@router.put("/account-groups/{group_id}")
def update_group(
    group_id: str, payload: GroupUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id, AccountGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail=_("error.group-not-found"))
    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    group.updated_at = datetime.now(UTC)
    db.commit()
    return {"status": "updated"}


@router.delete("/account-groups/{group_id}")
def delete_group(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id, AccountGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail=_("error.group-not-found"))
    db.query(GroupAccount).filter(GroupAccount.group_id == group_id).delete()
    db.delete(group)
    db.commit()
    return {"status": "deleted"}


@router.post("/account-groups/{group_id}/accounts/{account_id}")
def add_account_to_group(
    group_id: str, account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id, AccountGroup.user_id == user.id).first()
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id, SocialAccount.user_id == user.id).first()
    if not group or not account:
        raise HTTPException(status_code=404, detail=_("error.group-or-account-not-found"))
    existing = (
        db.query(GroupAccount).filter(GroupAccount.group_id == group_id, GroupAccount.account_id == account_id).first()
    )
    if not existing:
        db.add(GroupAccount(group_id=group_id, account_id=account_id))
        db.commit()
    return {"status": "added"}


@router.delete("/account-groups/{group_id}/accounts/{account_id}")
def remove_account_from_group(
    group_id: str, account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    mapping = (
        db.query(GroupAccount).filter(GroupAccount.group_id == group_id, GroupAccount.account_id == account_id).first()
    )
    if not mapping:
        raise HTTPException(status_code=404, detail=_("error.mapping-not-found"))
    db.delete(mapping)
    db.commit()
    return {"status": "removed"}
