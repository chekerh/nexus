"""Shared dependencies for API routes."""
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.user import User
from ..models.api_key import ApiKey

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "nexus-dev-secret-change-in-production")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve user from Bearer token or API key."""
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Try API key first
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
    if api_key:
        user = db.query(User).filter(User.id == api_key.user_id).first()
        if user and user.is_active:
            api_key.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return user

    # Try JWT session token
    try:
        import jwt as pyjwt
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if user and user.is_active:
            return user
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of 401."""
    try:
        return get_current_user(credentials, authorization, db)
    except HTTPException:
        return None
