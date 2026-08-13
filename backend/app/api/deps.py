"""Shared dependencies for API routes."""

import hashlib
import logging
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.i18n import _
from ..models.api_key import ApiKey
from ..models.user import Tenant, User

logger = logging.getLogger("nexus.auth")

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    authorization: str | None = Header(None),
    nexus_token: str | None = Cookie(None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve user from Bearer token, httpOnly cookie, or API key."""
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif nexus_token:
        token = nexus_token

    if not token:
        raise HTTPException(status_code=401, detail=_("error.not-auth"))

    # Try API key first
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active).first()
    if api_key:
        user = db.query(User).filter(User.id == api_key.user_id).first()
        if user and user.is_active:
            # Track last usage for audit
            api_key.last_used_at = datetime.now(UTC)
            db.commit()
            return user

    # Try JWT session token
    try:
        import jwt as pyjwt

        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if user and user.is_active:
            return user
    except pyjwt.ExpiredSignatureError:
        logger.warning("Expired JWT token")
        raise HTTPException(status_code=401, detail=_("error.token-expired")) from None
    except pyjwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token: %s", e)
        raise HTTPException(status_code=401, detail=_("error.invalid-token")) from None

    raise HTTPException(status_code=401, detail=_("error.invalid-token"))


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    authorization: str | None = Header(None),
    nexus_token: str | None = Cookie(None),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of 401."""
    try:
        return get_current_user(credentials, authorization, nexus_token, db)
    except HTTPException:
        return None


def get_current_tenant(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tenant | None:
    """Resolve the tenant for the current user."""
    if not user.tenant_id:
        return None
    return db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
