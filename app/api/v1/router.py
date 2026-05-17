"""
v1 API router — assembles all v1 endpoint routers into one include-able router.

Imported once in app/main.py:
    from app.api.v1.router import v1_router
    app.include_router(v1_router, prefix="/api/v1")
"""
from fastapi import APIRouter

from app.api.v1.endpoints.analysis import router as analysis_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.ingestion import router as ingestion_router

v1_router = APIRouter()

v1_router.include_router(analysis_router, prefix="/analysis")
v1_router.include_router(health_router,   prefix="/health")
v1_router.include_router(ingestion_router, prefix="/ingestion")
