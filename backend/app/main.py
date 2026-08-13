"""Nexus-UGC: AI-powered UGC production system.

FastAPI application entry point. Mounts the v1 API, legacy API, and frontend.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.v1.router import router as v1_router
from .core.config import settings
from .core.database import SessionLocal, init_db
from .core.i18n import I18nMiddleware
from .core.logging import configure_logging
from .core.middleware import (
    ERR_CODES,
    CorrelationIDMiddleware,
    CSRFTokenMiddleware,
    MaxUploadSizeMiddleware,
    PrometheusMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from .services.billing import HAS_STRIPE
from .services.job_queue import job_queue

logger = logging.getLogger("nexus")

configure_logging(
    level="DEBUG" if settings.DEV_RELOAD else "INFO",
    structured=settings.LOG_FORMAT == "structured",
)

# Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN", settings.SENTRY_DSN)
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                FastApiIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logger.info("Sentry initialized")
    except ImportError:
        logger.warning("sentry_sdk not installed — skipping Sentry init")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    await startup()
    yield
    await shutdown()


app = FastAPI(
    title="Nexus-UGC",
    version="2.0.0",
    description="AI-powered UGC production system — local or cloud.",
    lifespan=lifespan,
)

# CORS — zero-trust: never allow wildcard when credentials or cookies are in use.
# When PUBLIC_BASE_URL is set (production), CORS_ORIGINS must be explicit.
origins = (
    ["*"]
    if settings.CORS_ORIGINS == "*" and not settings.PUBLIC_BASE_URL
    else [o.strip() for o in settings.CORS_ORIGINS.split(",")]
)

allow_creds = origins != ["*"]
if not allow_creds:
    logger.warning("CORS allow_origins=* — cookies and credentials disabled. Set CORS_ORIGINS for production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Requested-With"],
    expose_headers=["X-CSRF-Token", "X-CSRF-Token-Rotated"],
    allow_credentials=allow_creds,
)

app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    general_limit=settings.RATE_LIMIT_PER_MINUTE,
    auth_limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
)
app.add_middleware(
    MaxUploadSizeMiddleware,
    max_size_mb=settings.MAX_UPLOAD_SIZE_MB,
)
app.add_middleware(CSRFTokenMiddleware)

os.makedirs(os.path.join(settings.UPLOAD_DIR, "clips"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "backgrounds"), exist_ok=True)

app.include_router(v1_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": ERR_CODES.get("internal_error", "INT-001")},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    request_id = getattr(request.state, "request_id", "")
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": ERR_CODES.get("internal_error", "INT-001"),
            "request_id": request_id,
        },
    )


async def startup():
    init_db()

    import asyncio

    from .api.v1.oauth import cleanup_stale_states

    async def _oauth_cleanup_loop():
        while True:
            await asyncio.sleep(300)
            cleanup_stale_states()

    async def _trial_expiry_loop():
        while True:
            await asyncio.sleep(3600)
            from .services.trial import expire_trials

            expired = expire_trials()
            if expired:
                logger.info("Expired %d trials", len(expired))

    async def _dunning_loop():
        while True:
            await asyncio.sleep(3600)
            from .services.dunning import process_dunning_queue

            process_dunning_queue()

    asyncio.create_task(_oauth_cleanup_loop())
    asyncio.create_task(_trial_expiry_loop())
    asyncio.create_task(_dunning_loop())

    from .workers.pipeline import run_pipeline

    job_queue.reap_stale_jobs()
    job_queue.set_pipeline_runner(run_pipeline)
    job_queue.start_worker()

    from .services.scheduler import post_scheduler

    post_scheduler.start()

    backend = (settings.ANALYSIS_BACKEND or "ollama").strip().lower()
    if backend == "airllm" and settings.AIRLLM_WARM_ON_START:
        from .core.airllm_service import airllm_service

        ok, message = airllm_service.ensure_loaded()
        logger.info("airllm warmup: %s | %s", "ready" if ok else "fallback-to-ollama", message)

    logger.info("Stripe: %s", "connected" if HAS_STRIPE else "not configured (local mode)")

    _provision_system_accounts()


def _provision_system_accounts():
    """Auto-create system-level social accounts from .env credentials."""
    if not settings.SYSTEM_ACCOUNTS_ENABLED:
        return

    from .core.security import encrypt_token
    from .models.account import SocialAccount
    from .models.user import User

    db = SessionLocal()
    try:
        system_user = db.query(User).filter(User.email == "admin@nexusugc.com").first()
        if not system_user:
            logger.warning("No admin user found for system accounts — skipping")
            return

        platform_configs = [
            (
                "youtube",
                settings.SYSTEM_YOUTUBE_REFRESH_TOKEN,
                {
                    "oauth_refresh_token_enc": encrypt_token(settings.SYSTEM_YOUTUBE_REFRESH_TOKEN)
                    if settings.SYSTEM_YOUTUBE_REFRESH_TOKEN
                    else "",
                },
            ),
            (
                "tiktok",
                settings.SYSTEM_TIKTOK_ACCESS_TOKEN,
                {
                    "tiktok_access_token_enc": encrypt_token(settings.SYSTEM_TIKTOK_ACCESS_TOKEN)
                    if settings.SYSTEM_TIKTOK_ACCESS_TOKEN
                    else "",
                    "tiktok_refresh_token_enc": encrypt_token(settings.SYSTEM_TIKTOK_REFRESH_TOKEN)
                    if settings.SYSTEM_TIKTOK_REFRESH_TOKEN
                    else "",
                    "tiktok_open_id": settings.SYSTEM_TIKTOK_OPEN_ID or "",
                },
            ),
            (
                "instagram",
                settings.SYSTEM_INSTAGRAM_ACCESS_TOKEN,
                {
                    "instagram_access_token_enc": encrypt_token(settings.SYSTEM_INSTAGRAM_ACCESS_TOKEN)
                    if settings.SYSTEM_INSTAGRAM_ACCESS_TOKEN
                    else "",
                    "instagram_user_id": settings.SYSTEM_INSTAGRAM_USER_ID or "",
                },
            ),
            (
                "twitter",
                settings.SYSTEM_TWITTER_ACCESS_TOKEN,
                {
                    "twitter_access_token_enc": encrypt_token(settings.SYSTEM_TWITTER_ACCESS_TOKEN)
                    if settings.SYSTEM_TWITTER_ACCESS_TOKEN
                    else "",
                    "twitter_user_id": settings.SYSTEM_TWITTER_USER_ID or "",
                },
            ),
            (
                "facebook",
                settings.SYSTEM_FACEBOOK_ACCESS_TOKEN,
                {
                    "facebook_access_token_enc": encrypt_token(settings.SYSTEM_FACEBOOK_ACCESS_TOKEN)
                    if settings.SYSTEM_FACEBOOK_ACCESS_TOKEN
                    else "",
                    "facebook_page_id": settings.SYSTEM_FACEBOOK_PAGE_ID or "",
                },
            ),
            (
                "linkedin",
                settings.SYSTEM_LINKEDIN_ACCESS_TOKEN,
                {
                    "linkedin_access_token_enc": encrypt_token(settings.SYSTEM_LINKEDIN_ACCESS_TOKEN)
                    if settings.SYSTEM_LINKEDIN_ACCESS_TOKEN
                    else "",
                    "linkedin_user_id": settings.SYSTEM_LINKEDIN_USER_ID or "",
                },
            ),
        ]

        created = 0
        for platform, token, extra_fields in platform_configs:
            if not token:
                continue
            existing = (
                db.query(SocialAccount)
                .filter(
                    SocialAccount.user_id == system_user.id,
                    SocialAccount.platform == platform,
                    SocialAccount.account_name == f"System {platform.title()}",
                )
                .first()
            )
            if existing:
                continue
            account = SocialAccount(
                user_id=system_user.id,
                platform=platform,
                account_name=f"System {platform.title()}",
                auth_mode="oauth",
                is_active=True,
                **extra_fields,
            )
            db.add(account)
            created += 1

        if created:
            db.commit()
            logger.info("Auto-provisioned %d system account(s)", created)
        else:
            logger.info("System accounts already provisioned or no credentials configured")
    except Exception as e:
        logger.warning("Could not provision system accounts: %s", e)
    finally:
        db.close()


async def shutdown():
    job_queue.stop_worker(timeout=30)
    from .services.scheduler import post_scheduler

    post_scheduler.stop()
    logger.info("Workers stopped")


@app.get("/health")
async def health():
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "2.0.0",
        "database": "connected" if db_ok else "unreachable",
    }


FRONTEND_DIR = settings.FRONTEND_DIR
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
