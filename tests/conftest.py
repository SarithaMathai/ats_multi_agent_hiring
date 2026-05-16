"""
Shared pytest fixtures for all test layers (unit, integration, e2e).
Fixtures here are available to every test without explicit imports.
"""

import pytest
from httpx import AsyncClient


# ── Markers ───────────────────────────────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast, in-process tests with no external deps")
    config.addinivalue_line("markers", "integration: tests that require running DB / services")
    config.addinivalue_line("markers", "e2e: full-stack tests against the running app")


# ── App client (placeholder — wire up once app.main exists) ───────────────────
@pytest.fixture
async def client():
    """Async HTTP client for API-level tests."""
    # from app.main import app
    # async with AsyncClient(app=app, base_url="http://test") as ac:
    #     yield ac
    yield None  # placeholder until app.main is implemented
