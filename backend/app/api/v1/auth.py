"""Authentication and user management API."""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...core.middleware import generate_csrf_token, hash_password, sanitize_html, verify_password
from ...models.api_key import ApiKey
from ...models.invite_key import InviteKey
from ...models.user import SubscriptionTier, User
from ...services.email import send_email
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_MARKER = os.path.join(settings.UPLOAD_DIR, ".admin_created")


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""
    invite_key: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class ApiKeyCreate(BaseModel):
    name: str = ""


class GoogleAuthConfigResponse(BaseModel):
    enabled: bool
    client_id: str = ""


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "tier": user.subscription_tier.value,
        "credits_used": user.credits_used_month,
        "credits_limit": user.credits_limit_month,
        "is_verified": user.is_verified,
    }


def _create_jwt(user_id: str, tenant_id: str | None = None) -> str:
    try:
        import jwt as pyjwt

        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(hours=settings.JWT_EXPIRY_HOURS),
            "iss": "nexus-ugc",
            "jti": secrets.token_urlsafe(16),
        }
        if tenant_id:
            payload["tenant"] = tenant_id
        return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    except ImportError:
        return "jwt-lib-not-installed"


def _is_first_user() -> bool:
    return not os.path.exists(ADMIN_MARKER)


def _seal_admin_created(user_id: str) -> None:
    with open(ADMIN_MARKER, "w") as f:
        f.write(user_id)


def _validate_invite_key(db: Session, code: str) -> InviteKey:
    if not code:
        raise HTTPException(status_code=400, detail=_("error.invite-key-required"))
    key = db.query(InviteKey).filter(InviteKey.code == code, InviteKey.is_active).first()
    if not key:
        raise HTTPException(status_code=400, detail=_("error.invalid-invite-key"))
    expires = key.expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires and expires < datetime.now(UTC):
        raise HTTPException(status_code=400, detail=_("error.invite-key-expired"))
    if (key.used_count or 0) >= key.max_uses:
        raise HTTPException(status_code=400, detail=_("error.invite-key-exhausted"))
    key.used_count = (key.used_count or 0) + 1
    db.commit()
    return key


def _set_token_cookie(response: Response, token: str):
    """Set httpOnly JWT cookie for browser-based auth."""
    max_age = settings.JWT_EXPIRY_HOURS * 3600
    response.set_cookie(
        key="nexus_token",
        value=token,
        max_age=max_age,
        path="/",
        secure=bool(settings.PUBLIC_BASE_URL),  # True in prod with HTTPS
        httponly=True,
        samesite="strict",
    )


@router.get("/google-config", response_model=GoogleAuthConfigResponse)
def google_config():
    return GoogleAuthConfigResponse(enabled=bool(settings.GOOGLE_CLIENT_ID), client_id=settings.GOOGLE_CLIENT_ID)


@router.post("/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail=_("error.password-too-short"))

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail=_("error.email-taken"))

    is_first = _is_first_user()
    if not is_first:
        _validate_invite_key(db, payload.invite_key)

    pw_hash, pw_salt = hash_password(payload.password)

    verification_token = secrets.token_urlsafe(48) if not is_first else ""
    user = User(
        email=sanitize_html(payload.email),
        password_hash=pw_hash,
        password_salt=pw_salt,
        display_name=sanitize_html(payload.display_name or payload.email.split("@")[0]),
        subscription_tier=SubscriptionTier.ENTERPRISE if is_first else SubscriptionTier.FREE,
        credits_limit_month=99999 if is_first else 5,
        is_verified=is_first,
        verification_token=hashlib.sha256(verification_token.encode()).hexdigest() if verification_token else "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if is_first:
        _seal_admin_created(user.id)

    token = _create_jwt(user.id)
    _set_token_cookie(response, token)

    if verification_token:
        verify_url = f"{settings.PUBLIC_BASE_URL}/verify-email.html?token={verification_token}" if settings.PUBLIC_BASE_URL else f"/api/v1/auth/verify-email?token={verification_token}"
        send_email(
            user.email,
            "Verify Your Email — Nexus-UGC",
            f"<h2>Welcome to Nexus-UGC!</h2><p>Verify your email: <a href='{verify_url}'>{verify_url}</a></p>",
        )
    return TokenResponse(token=token, user=_user_dict(user))


@router.post("/google")
def google_auth(payload: GoogleAuthRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate or register with a Google ID token."""
    try:
        import google.auth.transport.requests
        from google.oauth2 import id_token
    except ImportError:
        raise HTTPException(
            status_code=500, detail=_("error.google-auth-missing")
        ) from None

    try:
        info = id_token.verify_oauth2_token(
            payload.id_token,
            google.auth.transport.requests.Request(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=_("error.invalid-google-token").format(error=e)) from None

    google_id = info.get("sub")
    email = info.get("email", "")
    name = info.get("name", "")
    if not email:
        raise HTTPException(status_code=400, detail=_("error.google-no-email"))

    user = db.query(User).filter((User.google_id == google_id) | (User.email == email)).first()

    if user:
        if not user.is_active:
            raise HTTPException(status_code=403, detail=_("error.account-disabled"))
        if user.google_id != google_id:
            user.google_id = google_id
            db.commit()
    else:
        if settings.INVITE_REQUIRED_FOR_GOOGLE:
            raise HTTPException(status_code=400, detail=_("error.invite-key-required-for-google"))

        user = User(
            email=email,
            google_id=google_id,
            display_name=name or email.split("@")[0],
            subscription_tier=SubscriptionTier.FREE,
            password_hash="",
            password_salt="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = _create_jwt(user.id, user.tenant_id)
    _set_token_cookie(response, token)
    return TokenResponse(token=token, user=_user_dict(user))


@router.get("/csrf-token")
def get_csrf_token():
    token = generate_csrf_token()
    return {"csrf_token": token}


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash, user.password_salt):
        raise HTTPException(status_code=401, detail=_("error.invalid-credentials"))

    if not user.is_active:
        raise HTTPException(status_code=403, detail=_("error.account-disabled"))

    token = _create_jwt(user.id, user.tenant_id)
    _set_token_cookie(response, token)
    return TokenResponse(token=token, user=_user_dict(user))


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return _user_dict(user) | {"created_at": user.created_at.isoformat()}


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
    return {
        "api_keys": [
            {
                "id": k.id,
                "name": k.name,
                "created_at": k.created_at.isoformat(),
                "last_used": k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in keys
        ]
    }


@router.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail=_("error.api-key-not-found"))
    key.is_active = False
    db.commit()
    return {"status": "revoked"}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset email with a time-limited token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return {"message": "If that email is registered, a reset link has been sent."}
    token = secrets.token_urlsafe(48)
    user.reset_token = hashlib.sha256(token.encode()).hexdigest()
    user.reset_token_expires = datetime.now(UTC) + timedelta(hours=1)
    db.commit()
    reset_url = f"{settings.PUBLIC_BASE_URL}/reset-password.html?token={token}" if settings.PUBLIC_BASE_URL else f"/reset-password.html?token={token}"
    send_email(
        user.email,
        "Reset Your Password — Nexus-UGC",
        f"<h2>Password Reset</h2><p>Click to reset: <a href='{reset_url}'>{reset_url}</a></p><p>Link expires in 1 hour.</p>",
    )
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using a time-limited token."""
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = db.query(User).filter(User.reset_token == token_hash).first()
    if not user:
        raise HTTPException(status_code=400, detail=_("error.invalid-reset-token"))
    if not user.reset_token_expires or user.reset_token_expires < datetime.now(UTC):
        raise HTTPException(status_code=400, detail=_("error.reset-token-expired"))
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail=_("error.password-too-short"))
    pw_hash, pw_salt = hash_password(payload.password)
    user.password_hash = pw_hash
    user.password_salt = pw_salt
    user.reset_token = ""
    user.reset_token_expires = None
    db.commit()
    return {"message": "Password reset successfully"}


@router.post("/send-verification")
def send_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send email verification link."""
    if user.is_verified:
        return {"message": "Email already verified"}
    token = secrets.token_urlsafe(48)
    user.verification_token = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    verify_url = f"{settings.PUBLIC_BASE_URL}/verify-email.html?token={token}" if settings.PUBLIC_BASE_URL else f"/api/v1/auth/verify-email?token={token}"
    send_email(
        user.email,
        "Verify Your Email — Nexus-UGC",
        f"<h2>Welcome to Nexus-UGC!</h2><p>Verify your email: <a href='{verify_url}'>{verify_url}</a></p>",
    )
    return {"message": "Verification email sent"}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email address using token."""
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = db.query(User).filter(User.verification_token == token_hash).first()
    if not user:
        raise HTTPException(status_code=400, detail=_("error.invalid-verification-token"))
    user.is_verified = True
    user.verification_token = ""
    db.commit()
    return {"message": "Email verified successfully", "email": user.email}


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update display name and/or password."""
    if payload.display_name is not None:
        user.display_name = sanitize_html(payload.display_name)
    if payload.new_password:
        if not payload.current_password:
            raise HTTPException(status_code=400, detail=_("error.current-password-required"))
        if not verify_password(payload.current_password, user.password_hash, user.password_salt):
            raise HTTPException(status_code=403, detail=_("error.current-password-incorrect"))
        if len(payload.new_password) < 8:
            raise HTTPException(status_code=400, detail=_("error.new-password-too-short"))
        pw_hash, pw_salt = hash_password(payload.new_password)
        user.password_hash = pw_hash
        user.password_salt = pw_salt
    db.commit()
    return _user_dict(user) | {"message": "Profile updated"}


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    """Get extended user profile."""
    return _user_dict(user) | {
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "is_verified": user.is_verified,
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
    }
