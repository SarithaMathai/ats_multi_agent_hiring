"""
Health-check endpoints.

GET /api/v1/health          — overall system status
GET /api/v1/health/chroma   — ChromaDB connectivity
GET /api/v1/health/db       — PostgreSQL connectivity
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter

from configs.settings import settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


# ── Response helpers ──────────────────────────────────────────────────────────

def _ok(service: str, detail: str = "reachable") -> dict[str, Any]:
    return {"service": service, "status": "ok", "detail": detail}


def _fail(service: str, detail: str) -> dict[str, Any]:
    return {"service": service, "status": "error", "detail": detail}


# ── ChromaDB probe ────────────────────────────────────────────────────────────

async def _probe_chroma() -> dict[str, Any]:
    try:
        from vector_store.chroma.client import get_chroma_client
        client = await asyncio.to_thread(get_chroma_client)
        await asyncio.to_thread(client.heartbeat)
        return _ok("chroma", f"{settings.chroma.base_url} reachable")
    except Exception as exc:
        return _fail("chroma", str(exc))


# ── PostgreSQL probe ──────────────────────────────────────────────────────────

async def _probe_db() -> dict[str, Any]:
    try:
        import asyncpg
        conn = await asyncpg.connect(settings.database.url.replace("+asyncpg", ""),
                                     timeout=3)
        await conn.close()
        return _ok("postgresql", f"{settings.database.host}:{settings.database.port}")
    except Exception as exc:
        return _fail("postgresql", str(exc))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/chroma")
async def health_chroma() -> dict[str, Any]:
    """ChromaDB connectivity probe."""
    return await _probe_chroma()


@router.get("/db")
async def health_db() -> dict[str, Any]:
    """PostgreSQL connectivity probe."""
    return await _probe_db()


@router.get("")
async def health_overall() -> dict[str, Any]:
    """Overall system health — probes all dependencies in parallel."""
    chroma_result, db_result = await asyncio.gather(
        _probe_chroma(),
        _probe_db(),
    )
    checks = [chroma_result, db_result]
    overall = "ok" if all(c["status"] == "ok" for c in checks) else "degraded"
    return {
        "status": overall,
        "version": "0.1.0",
        "environment": settings.app_env,
        "checks": checks,
    }
