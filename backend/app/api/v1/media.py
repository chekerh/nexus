"""Authenticated media file serving."""

import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.i18n import _
from ...models.api_key import ApiKey
from ...models.user import User

router = APIRouter(prefix="/media", tags=["media"])


def _token_from_request(request: Request) -> str | None:
    """Extract JWT from Authorization header, cookie, or query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    cookie = request.cookies.get("nexus_token")
    if cookie:
        return cookie
    return request.query_params.get("token")


def _resolve_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail=_("error.not-auth"))

    key_hash = hashlib.sha256(token.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active).first()
    if api_key:
        user = db.query(User).filter(User.id == api_key.user_id, User.is_active).first()
        if user:
            return user

    try:
        import jwt as pyjwt

        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user = db.query(User).filter(User.id == payload["sub"], User.is_active).first()
        if user:
            return user
    except Exception:
        pass

    raise HTTPException(status_code=401, detail=_("error.invalid-token"))


@router.get("/{path:path}")
def serve_media(path: str, user: User = Depends(_resolve_user)):
    upload = os.path.abspath(settings.UPLOAD_DIR)
    full = os.path.abspath(os.path.join(upload, path))
    if not full.startswith(upload + os.sep) and full != upload:
        raise HTTPException(status_code=400, detail=_("error.invalid-path"))
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail=_("error.file-not-found"))
    return FileResponse(full)
