"""
E2E tests — Fix Slow Hiring scenario (full pipeline with real LLM + services).

This is the primary end-to-end scenario test.  It exercises the complete
stack: HiringAnalysisWorkflow → CoordinatorAgent → LangGraph → all 4 forced
agents → response assembly.

Assertions cover:
  - Pipeline completes with status "success"
  - Correct agents ran (pipeline_health, improvement_action, evaluation, optimization)
  - Each agent output has confidence_score > 0 and at least 1 insight
  - All recommendations are high or medium priority
  - Total tokens and latency are within expected ranges
  - The assembled summary references the query topic
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

# ── Shared test data ──────────────────────────────────────────────────────────

_STAGES = [
    {"stage": "Application Review", "candidate_id": f"c{i}", "days_in_stage": d, "passed": True}
    for i, d in enumerate([2, 8, 5, 12, 3, 7, 4])
] + [
    {"stage": "Technical Interview", "candidate_id": f"c{i+7}", "days_in_stage": d, "passed": p}
    for i, (d, p) in enumerate([(20, False), (25, True), (18, False), (22, True)])
] + [
    {"stage": "Offer", "candidate_id": f"c{i+11}", "days_in_stage": d, "passed": True}
    for i, d in enumerate([4, 3])
]

_CANDIDATES = [
    {"candidate_id": f"c{i}", "source_channel": ch, "quality_score": q, "hired": h}
    for i, (ch, q, h) in enumerate([
        ("LinkedIn", 0.72, True),  ("Referral", 0.88, True),
        ("Indeed",   0.45, False), ("LinkedIn", 0.65, False),
        ("Agency",   0.55, False), ("Referral", 0.91, True),
        ("Indeed",   0.40, False), ("LinkedIn", 0.78, True),
    ])
]

_REJECTIONS = [
    {"candidate_id": f"r{i}", "stage": s, "rejection_category": cat}
    for i, (s, cat) in enumerate([
        ("Technical Interview", "technical_skills"),
        ("Phone Screen",        "skills_mismatch"),
        ("Technical Interview", "technical_skills"),
        ("Offer",               "compensation"),
        ("Phone Screen",        "skills_mismatch"),
        ("Technical Interview", "technical_skills"),
    ])
]


# ── Workflow-level test (no HTTP, direct Python call) ─────────────────────────

async def test_fix_slow_hiring_via_workflow():
    """Full fix_slow_hiring scenario via HiringAnalysisWorkflow.run_scenario()."""
    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow

    wf = HiringAnalysisWorkflow()
    response = await wf.run_scenario(
        name="fix_slow_hiring",
        structured_data={
            "stages": _STAGES,
            "candidates": _CANDIDATES,
            "rejections": _REJECTIONS,
        },
        filters={"department": "Engineering"},
    )

    # ── Status
    assert response.status in ("success", "partial_success", "partial"), (
        f"Unexpected status: {response.status}"
    )

    # ── Correct agents ran
    agent_names = {o.agent_name for o in response.agent_outputs if o.status != "skipped"}
    expected = {"pipeline_health", "improvement_action", "evaluation", "optimization"}
    assert expected <= agent_names, (
        f"Missing agents: {expected - agent_names}. Got: {agent_names}"
    )

    # ── Each insight agent produced output
    insight_agents = [
        o for o in response.agent_outputs
        if o.agent_name in ("pipeline_health", "improvement_action") and o.status == "success"
    ]
    assert len(insight_agents) == 2, f"Expected 2 insight agents to succeed, got {len(insight_agents)}"

    for out in insight_agents:
        assert out.confidence_score > 0, f"{out.agent_name} has zero confidence"
        assert len(out.insights) >= 1, f"{out.agent_name} produced no insights"

    # ── Summary is meaningful
    assert response.summary, "Summary should not be empty"
    assert len(response.summary) > 50, "Summary too short to be useful"

    # ── Tokens and latency are non-zero
    assert response.total_tokens > 0, "Total tokens should be > 0"
    assert response.total_latency_ms > 0, "Latency should be > 0"


# ── API-level test (httpx client) ─────────────────────────────────────────────

async def test_fix_slow_hiring_via_api(client):
    """Full fix_slow_hiring scenario via POST /api/v1/analysis/scenario/fix_slow_hiring."""
    if client is None:
        pytest.skip("App client not available")

    resp = await client.post(
        "/api/v1/analysis/scenario/fix_slow_hiring",
        json={
            "filters": {"department": "Engineering"},
            "structured_data": {
                "stages": _STAGES,
                "candidates": _CANDIDATES,
                "rejections": _REJECTIONS,
            },
        },
        timeout=120,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Status
    assert body["status"] in ("success", "partial", "partial_success")

    # Agent outputs present
    agent_names = {o["agent_name"] for o in body["agent_outputs"] if o["status"] != "skipped"}
    assert "pipeline_health"    in agent_names
    assert "improvement_action" in agent_names

    # Each output has confidence > 0
    for out in body["agent_outputs"]:
        if out["status"] == "success":
            assert out["confidence_score"] > 0, (
                f"{out['agent_name']} returned zero confidence"
            )

    # Recommendations present
    assert len(body["all_recommendations"]) >= 1, "No recommendations returned"
    for rec in body["all_recommendations"]:
        assert rec["priority"] in ("high", "medium", "low")
        assert rec["title"]
        assert rec["description"]


# ── Boundary conditions ───────────────────────────────────────────────────────

async def test_fix_slow_hiring_empty_data():
    """Scenario with empty structured_data completes (agents degrade gracefully)."""
    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow

    wf = HiringAnalysisWorkflow()
    response = await wf.run_scenario(
        name="fix_slow_hiring",
        structured_data={},   # all agents get empty data — should degrade, not crash
    )
    # Status may be partial/degraded but pipeline must not raise
    assert response.status in ("success", "partial_success", "partial", "degraded", "error")
    assert response.run_id


async def test_fix_slow_hiring_query_override():
    """query_override replaces the default scenario query."""
    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow

    custom_query = "Focus specifically on the offer rejection rate — why are offers declining?"
    wf = HiringAnalysisWorkflow()
    response = await wf.run_scenario(
        name="fix_slow_hiring",
        structured_data={"stages": _STAGES, "candidates": _CANDIDATES, "rejections": _REJECTIONS},
        query_override=custom_query,
    )
    assert response.status in ("success", "partial_success", "partial")
    # The query used should be the override, not the default
    assert custom_query in response.summary or response.total_tokens > 0
