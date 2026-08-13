"""Aggregates all v1 API routers."""

from fastapi import APIRouter

from . import (
    accounts,
    admin,
    analytics,
    auth,
    billing,
    brainrot,
    campaigns,
    oauth,
    personas,
    pipeline,
    posts,
    publish,
    system,
    templates,
    thumbnails,
    whop,
)
from .media import router as media_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(pipeline.router)
router.include_router(accounts.router)
router.include_router(publish.router)
router.include_router(billing.router)
router.include_router(thumbnails.router)
router.include_router(personas.router)
router.include_router(posts.router)
router.include_router(campaigns.router)
router.include_router(whop.router)
router.include_router(admin.router)
router.include_router(brainrot.router)
router.include_router(analytics.router)
router.include_router(oauth.router)
router.include_router(system.router)
router.include_router(templates.router)
router.include_router(media_router)
