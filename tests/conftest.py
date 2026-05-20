"""
Shared pytest fixtures — available to every test without explicit imports.

Fixture tiers:
  Unit        — no external services (pure Python)
  Integration — requires PostgreSQL + ChromaDB running
  E2E         — requires full stack (FastAPI app in-process via httpx)
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ── Markers ───────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast, in-process tests with no external deps")
    config.addinivalue_line("markers", "integration: tests that require running DB / ChromaDB")
    config.addinivalue_line("markers", "e2e: full-stack tests using the FastAPI app in-process")


# ── FastAPI app client ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    """Async httpx client wired directly to the FastAPI app (no server needed)."""
    from app.main import app, lifespan
    async with lifespan(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ── Reusable structured data ──────────────────────────────────────────────────

@pytest.fixture
def stages():
    return [
        {"stage": "Application Review", "candidate_id": f"c{i}", "days_in_stage": d, "passed": True}
        for i, d in enumerate([2, 8, 5, 12, 3])
    ] + [
        {"stage": "Technical Interview", "candidate_id": f"c{i+5}", "days_in_stage": d, "passed": p}
        for i, (d, p) in enumerate([(18, False), (22, True), (15, False)])
    ]


@pytest.fixture
def candidates():
    return [
        {"candidate_id": f"c{i}", "source_channel": ch, "quality_score": q, "hired": h}
        for i, (ch, q, h) in enumerate([
            ("LinkedIn", 0.72, True),  ("Referral", 0.88, True),
            ("Indeed",   0.45, False), ("LinkedIn", 0.65, False),
            ("Agency",   0.55, False), ("Referral", 0.91, True),
        ])
    ]


@pytest.fixture
def rejections():
    return [
        {"candidate_id": f"r{i}", "stage": s, "rejection_category": cat}
        for i, (s, cat) in enumerate([
            ("Technical Interview", "technical_skills"),
            ("Phone Screen",        "skills_mismatch"),
            ("Technical Interview", "technical_skills"),
            ("Offer",               "compensation"),
            ("Phone Screen",        "skills_mismatch"),
        ])
    ]


@pytest.fixture
def interviewers():
    return [
        {"interviewer_id": f"i{i}", "name": n, "interviews_assigned": c, "avg_rating": r}
        for i, (n, c, r) in enumerate([
            ("Alice", 18, 4.5), ("Bob", 5, 4.2),
            ("Carol", 22, 3.8), ("Dave", 3, 4.7),
        ])
    ]


@pytest.fixture
def offers():
    return [
        {"candidate_id": f"o{i}", "position": pos, "offered": True, "accepted": acc, "decline_reason": dr}
        for i, (pos, acc, dr) in enumerate([
            ("SWE", True, None), ("SWE", False, "compensation"),
            ("PM",  True, None), ("PM",  False, "compensation"),
            ("DS",  True, None), ("DS",  False, "competing offer"),
        ])
    ]


@pytest.fixture
def all_structured_data(stages, candidates, rejections, interviewers, offers):
    return {
        "stages": stages,
        "candidates": candidates,
        "rejections": rejections,
        "interviewers": interviewers,
        "offers": offers,
    }
