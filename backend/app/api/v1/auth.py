"""Authentication and user management API."""
import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.config import settings
from ...models.user import User, SubscriptionTier
from ...models.api_key import ApiKey
from ..deps import get_current_user, JWT_SECRET

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class ApiKeyCreate(BaseModel):
    name: str = ""


def _hash_password(password: str) -> str:
    salt = b"nexus_ugc_salt_v1"
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000).hex()


def _create_jwt(user_id: str) -> str:
    try:
        import jwt as pyjwt
        payload = {
            "sub": user_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        }
        return pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")
    except ImportError:
        return "jwt-lib-not-installed"


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=_hash_password(payload.password),
        display_name=payload.display_name or payload.email.split("@")[0],
        subscription_tier=SubscriptionTier.FREE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_jwt(user.id)
    return TokenResponse(
        token=token,
        user={"id": user.id, "email": user.email, "display_name": user.display_name,
              "tier": user.subscription_tier.value, "credits_used": user.credits_used_month,
              "credits_limit": user.credits_limit_month},
    )


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = _create_jwt(user.id)
    return TokenResponse(
        token=token,
        user={"id": user.id, "email": user.email, "display_name": user.display_name,
              "tier": user.subscription_tier.value, "credits_used": user.credits_used_month,
              "credits_limit": user.credits_limit_month},
    )


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id, "email": user.email, "display_name": user.display_name,
        "tier": user.subscription_tier.value, "credits_used": user.credits_used_month,
        "credits_limit": user.credits_limit_month,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/api-keys")
def create_api_key(payload: ApiKeyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    raw_key = "nex_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = ApiKey(user_id=user.id, key_hash=key_hash, name=payload.name)
    db.add(api_key)
    db.commit()
    return {"api_key": raw_key, "name": payload.name, "id": api_key.id}


@router.get("/api-keys")
def list_api_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).all()
    return {"api_keys": [{"id": k.id, "name": k.name, "created_at": k.created_at.isoformat(), "last_used": k.last_used_at.isoformat() if k.last_used_at else None} for k in keys]}


@router.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    db.commit()
    return {"status": "revoked"}
