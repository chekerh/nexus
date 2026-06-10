"""Aggregates all v1 API routers."""
from fastapi import APIRouter
from . import auth, pipeline, accounts, publish, billing

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(pipeline.router)
router.include_router(accounts.router)
router.include_router(publish.router)
router.include_router(billing.router)
