"""Security middleware: rate limiting, CSRF, security headers, input sanitization."""

import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

logger = logging.getLogger("nexus.middleware")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.csp_nonce = secrets.token_hex(16)

        response = await call_next(request)
        if settings.SECURITY_HEADERS_ENABLED:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

            csp = (
                "default-src 'self'; "
                "script-src 'self' https://accounts.google.com; "
                "style-src 'self' https://fonts.googleapis.com https://accounts.google.com; "
                "img-src 'self' data: blob:; "
                "media-src 'self'; font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self' https://accounts.google.com; "
                "frame-src 'self' https://accounts.google.com; "
                "form-action 'self'; frame-ancestors 'none'; base-uri 'self'; "
                f"worker-src 'self'; report-uri {settings.CSP_REPORT_URI}"
            )
            response.headers["Content-Security-Policy"] = csp

            if settings.HSTS_ENABLED:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            if not response.headers.get("Content-Type", "").startswith("text/html"):
                response.headers["X-Content-Type-Options"] = "nosniff"

        return response


ERR_CODES = {
    "auth_invalid": "AUTH-001",
    "auth_expired": "AUTH-002",
    "auth_required": "AUTH-003",
    "quota_exceeded": "QUOTA-001",
    "rate_limited": "RATE-001",
    "validation_error": "VAL-001",
    "not_found": "NOTFOUND-001",
    "processing_failed": "PROC-001",
    "upload_too_large": "UPLOAD-001",
    "csrf_failed": "CSRF-001",
    "internal_error": "INT-001",
}


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Adds or forwards X-Request-ID for request tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        # Inject request_id into the logging context
        old_factory = logging.getLogRecordFactory()

        def _add_request_id(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = getattr(request.state, "request_id", "")
            return record

        logging.setLogRecordFactory(_add_request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record HTTP request metrics (count, duration, status)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        status = str(response.status_code)
        from .metrics import http_request_duration_seconds, http_requests_total

        http_requests_total.labels(method=method, path=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiter with configurable backend (memory or database)."""

    def __init__(self, app, general_limit: int = 60, auth_limit: int = 10, window: int = 60):
        super().__init__(app)
        self.general_limit = general_limit
        self.auth_limit = auth_limit
        self.window = window
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        forwarded = request.headers.get("X-Forwarded-For", "")
        client_ip = (
            forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        )
        now = time.time()
        cutoff = now - self.window

        is_auth = request.url.path.startswith("/api/v1/auth/")
        limit = self.auth_limit if is_auth else self.general_limit

        backend = getattr(settings, "RATE_LIMIT_BACKEND", "memory")

        if backend == "database":
            return await self._check_db(limit, client_ip, request, call_next)
        return await self._check_memory(limit, client_ip, now, cutoff, request, call_next)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _check_memory(
        self, limit: int, client_ip: str, now: float, cutoff: float, request: Request, call_next: Callable
    ) -> Response:
        with self._lock:
            entries = [t for t in self._requests.get(client_ip, []) if t > cutoff]
            if len(self._requests) > 100000:
                stale_cutoff = now - 3600
                self._requests = defaultdict(
                    list, {k: [t for t in v if t > stale_cutoff] for k, v in self._requests.items()}
                )

            if len(entries) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Too many requests. Limit: {limit} per {self.window}s."},
                )

            entries.append(now)
            self._requests[client_ip] = entries
        return await call_next(request)

    async def _check_db(self, limit: int, client_ip: str, request: Request, call_next: Callable) -> Response:
        """DB-backed rate limit check. Cleans expired entries periodically."""
        from ..core.database import SessionLocal
        from ..models.rate_limit import RateLimitEntry

        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.window)

        db = SessionLocal()
        try:
            recent = (
                db.query(RateLimitEntry)
                .filter(
                    RateLimitEntry.ip == client_ip,
                    RateLimitEntry.expires_at > cutoff,
                )
                .count()
            )

            if recent >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Too many requests. Limit: {limit} per {self.window}s."},
                )

            entry = RateLimitEntry(
                id=str(uuid.uuid4()),
                ip=client_ip,
                path=request.url.path,
                expires_at=now + timedelta(seconds=self.window),
            )
            db.add(entry)

            # Clean expired entries every 100 writes
            cleanup = db.query(RateLimitEntry).filter(RateLimitEntry.expires_at <= now).limit(1000).all()
            if cleanup:
                for c in cleanup:
                    db.delete(c)

            db.commit()
        finally:
            db.close()

        return await call_next(request)


class MaxUploadSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length exceeding the configured limit."""

    def __init__(self, app, max_size_mb: int = 500):
        super().__init__(app)
        self.max_bytes = max_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_bytes:
                    max_mb = self.max_bytes // (1024 * 1024)
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request too large. Maximum size: {max_mb}MB."},
                    )
            except (ValueError, TypeError):
                pass
        return await call_next(request)


class CSRFTokenMiddleware(BaseHTTPMiddleware):
    """CSRF protection for cookie-based auth with single-use token rotation."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.CSRF_ENABLED:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return await call_next(request)

        if not request.cookies:
            return await call_next(request)

        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            return response

        # Exempt CSP violation reports (browser-initiated, no CSRF token)
        if request.url.path.endswith("/csp-violation-report"):
            return await call_next(request)

        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")

        if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed."},
            )

        response = await call_next(request)

        # Rotate the CSRF token after every state-mutating request (single-use)
        if response.status_code < 500:
            new_token = generate_csrf_token()
            response.set_cookie(
                key="csrf_token",
                value=new_token,
                path="/",
                samesite="strict",
                secure=bool(settings.PUBLIC_BASE_URL) or request.url.scheme == "https",
                httponly=False,  # accessible to JS for form submission
                max_age=settings.JWT_EXPIRY_HOURS * 3600,
            )
            response.headers["X-CSRF-Token-Rotated"] = new_token

        return response


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def sanitize_html(text: str) -> str:
    """Strip dangerous HTML/JS from user input using regex."""
    if not text:
        return text
    text = re.sub(r"<[^>]*>", "", text, flags=re.DOTALL)
    text = re.sub(r"on\w+\s*=\s*(['\">]|$)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"javascript\s*:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[<>]", "", text)
    return text


LEGACY_SALT = "nexus_ugc_salt_v1"


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash password with per-user random salt.

    Returns (hash_hex, salt_hex).
    """
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000)
    return key.hex(), salt


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """Verify password against stored hash+salt.

    Handles legacy (pre-salt) passwords by falling back to the old global salt.
    """
    if stored_salt:
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), stored_salt.encode(), 600000)
        return hmac.compare_digest(key.hex(), stored_hash)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), LEGACY_SALT.encode(), 100000)
    return hmac.compare_digest(key.hex(), stored_hash)
