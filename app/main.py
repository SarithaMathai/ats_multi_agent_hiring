"""
ATS Multi-Agent Hiring System — FastAPI application entry point.

Startup sequence (lifespan):
  1. Configure logging
  2. Initialise ChromaDB collections (async-wrapped sync call)
  3. Build the HiringAnalysisWorkflow singleton (compiles LangGraph graph)

All routers are mounted under /api/v1:
  /api/v1/analysis   — run queries and scenarios
  /api/v1/health     — system / dependency health checks
  /api/v1/ingestion  — CSV upload and ingestion status

Swagger UI: http://localhost:8080/docs
ReDoc:       http://localhost:8080/redoc
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.logging_middleware import LoggingMiddleware
from app.api.v1.router import v1_router
from configs.settings import settings

# ── Env fixes — must happen before any third-party client is created ─────────
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")  # silence ChromaDB/PostHog warning

logger = logging.getLogger("ats.main")

# ── Workflow singleton ─────────────────────────────────────────────────────────

_workflow = None


def get_workflow():
    """Return the shared HiringAnalysisWorkflow instance (set during lifespan)."""
    if _workflow is None:
        raise RuntimeError("Workflow not initialised — lifespan startup must complete first.")
    return _workflow


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before serving, teardown tasks on shutdown."""
    global _workflow

    # 1. Logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )
    logger.info("Starting ATS Multi-Agent Hiring System (env=%s)", settings.app_env)

    # 2. ChromaDB collections — capped at 10 s so a down server never blocks startup
    try:
        from vector_store.chroma.collection_manager import initialise_all_collections
        await asyncio.wait_for(
            asyncio.to_thread(initialise_all_collections),
            timeout=10.0,
        )
        logger.info("ChromaDB collections initialised.")
    except asyncio.TimeoutError:
        logger.warning("ChromaDB init timed out after 10 s — RAG will degrade gracefully.")
    except Exception as exc:
        logger.warning("ChromaDB init skipped (will degrade gracefully): %s", exc)

    # 3. Workflow singleton — builds LangGraph graph once
    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow
    _workflow = HiringAnalysisWorkflow()
    logger.info(
        "HiringAnalysisWorkflow ready. Scenarios: %s",
        _workflow.scenario_names(),
    )

    yield  # ← application serves requests between yield and the lines below

    logger.info("Shutting down ATS application.")
    _workflow = None


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="ATS Multi-Agent Hiring System",
    description=(
        "AI-powered multi-agent platform for hiring analytics. "
        "Exposes pipeline health, sourcing quality, rejection root-cause, "
        "resource optimisation, and offer-insight agents via a single REST API."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — wide open in development; restrict in production via env
_origins = ["*"] if settings.is_development else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(v1_router, prefix="/api/v1")


# ── Root redirect ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    return {
        "name": "ATS Multi-Agent Hiring System",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
