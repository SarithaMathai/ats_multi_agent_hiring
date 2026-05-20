"""
E2E tests — Analysis API endpoints.

Uses an in-process httpx client wired to the FastAPI app (no server required).
All tests make real LLM calls and hit real services (ChromaDB), so they are
marked e2e and will take 15–90 seconds total.

Each test asserts the HTTP contract (status codes, response shapes) as well as
basic semantic correctness (status != error, agents ran, summary non-empty).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


# ── Health endpoint ───────────────────────────────────────────────────────────

async def test_health_root(client):
    """GET /api/v1/health returns 200 with status field."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert body["version"] == "0.1.0"


async def test_health_chroma(client):
    """GET /api/v1/health/chroma returns 200 with service field."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.get("/api/v1/health/chroma")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "chroma"
    assert body["status"] in ("ok", "error")


async def test_health_db(client):
    """GET /api/v1/health/db returns 200 with service field."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.get("/api/v1/health/db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "postgresql"
    assert body["status"] in ("ok", "error")


# ── Scenarios list ────────────────────────────────────────────────────────────

async def test_list_scenarios(client):
    """GET /api/v1/analysis/scenarios returns all 5 registered scenarios."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.get("/api/v1/analysis/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert len(scenarios) == 5
    names = {s["name"] for s in scenarios}
    assert names == {
        "fix_slow_hiring", "balance_workload", "investigate_rejections",
        "executive_metrics", "interviewer_feedback",
    }
    for s in scenarios:
        assert "description" in s
        assert "agents" in s
        assert len(s["agents"]) >= 1


# ── POST /run — free-form ─────────────────────────────────────────────────────

async def test_run_analysis_free_form(client):
    """POST /run with a free-form query returns a valid CoordinatorResponse."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.post(
        "/api/v1/analysis/run",
        json={"query": "Where are the biggest bottlenecks in our hiring pipeline?", "filters": {}},
        timeout=120,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("success", "partial", "partial_success")
    assert body["run_id"]
    assert body["summary"]
    assert len(body["agent_outputs"]) >= 1


async def test_run_analysis_scenario_tagged(client):
    """POST /run with scenario tag bypasses RoutingAgent and uses forced agents."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.post(
        "/api/v1/analysis/run",
        json={
            "query": "Why is interviewer workload imbalanced?",
            "scenario": "balance_workload",
            "filters": {},
        },
        timeout=120,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("success", "partial", "partial_success")

    agent_names = {o["agent_name"] for o in body["agent_outputs"]}
    # With forced agents routing is skipped — these must be present
    assert "pipeline_health" in agent_names or "resource_optimization" in agent_names


async def test_run_analysis_unknown_scenario(client):
    """POST /run with a non-existent scenario falls back to free-form routing."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.post(
        "/api/v1/analysis/run",
        json={"query": "Show metrics", "scenario": "not_a_real_scenario", "filters": {}},
        timeout=120,
    )
    # The workflow skips forced_agents and lets RoutingAgent decide — should still succeed
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("success", "partial", "partial_success", "error")


# ── POST /scenario/{name} ─────────────────────────────────────────────────────

async def test_run_scenario_interviewer_feedback(client, interviewers):
    """POST /scenario/interviewer_feedback returns success with structured data."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.post(
        "/api/v1/analysis/scenario/interviewer_feedback",
        json={"filters": {}, "structured_data": {"interviewers": interviewers}},
        timeout=120,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("success", "partial", "partial_success")
    assert body["summary"]

    agent_names = {o["agent_name"] for o in body["agent_outputs"]}
    assert "resource_optimization" in agent_names


async def test_run_scenario_unknown_name(client):
    """POST /scenario/no_such_scenario returns 404."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.post(
        "/api/v1/analysis/scenario/no_such_scenario",
        json={"filters": {}, "structured_data": {}},
        timeout=30,
    )
    assert resp.status_code == 404
    assert "no_such_scenario" in resp.json()["detail"]


# ── GET /runs/{run_id} ────────────────────────────────────────────────────────

async def test_get_cached_run(client):
    """Run an analysis then retrieve it by run_id."""
    if client is None:
        pytest.skip("App client not available")

    run_resp = await client.post(
        "/api/v1/analysis/run",
        json={"query": "How is our sourcing performing?", "filters": {}},
        timeout=120,
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    get_resp = await client.get(f"/api/v1/analysis/runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["run_id"] == run_id


async def test_get_missing_run(client):
    """GET /runs/nonexistent returns 404."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.get("/api/v1/analysis/runs/does-not-exist-xyz")
    assert resp.status_code == 404


# ── Root ──────────────────────────────────────────────────────────────────────

async def test_root_endpoint(client):
    """GET / returns API info dict."""
    if client is None:
        pytest.skip("App client not available")
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["docs"] == "/docs"
    assert body["health"] == "/api/v1/health"
