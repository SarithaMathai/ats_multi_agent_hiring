"""
Day 11 smoke + LLM test — Orchestration: Workflows & Scenarios

Levels:
  1 (default) — imports, scenario registry, RunState, no LLM
  2            — run_scenario() for each of the 5 scenarios (real LLM)
  3            — run() via CoordinatorRequest free-form + scenario-tagged

Usage:
    .\run.bat scripts\test_day11.py              # Level 1 only
    .\run.bat scripts\test_day11.py --level 2    # Level 1 + 2
    .\run.bat scripts\test_day11.py --level 3    # Full suite
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

# ── shared fixture data ───────────────────────────────────────────────────────

STAGES = [
    {"stage": "Application Review", "candidate_id": f"c{i}", "days_in_stage": d, "passed": True}
    for i, d in enumerate([2, 3, 5, 8, 4, 6, 12, 7, 3, 9])
] + [
    {"stage": "Technical Interview", "candidate_id": f"c{i+10}", "days_in_stage": d, "passed": p}
    for i, (d, p) in enumerate([(15, False), (20, True), (18, False), (22, True), (16, False)])
]

CANDIDATES = [
    {"candidate_id": f"c{i}", "source_channel": ch, "quality_score": q, "hired": h}
    for i, (ch, q, h) in enumerate([
        ("LinkedIn", 0.72, True), ("LinkedIn", 0.65, False), ("Referral", 0.88, True),
        ("Indeed", 0.45, False), ("LinkedIn", 0.81, True), ("Referral", 0.91, True),
        ("Indeed", 0.38, False), ("Agency", 0.55, False), ("LinkedIn", 0.70, False),
        ("Referral", 0.85, True),
    ])
]

REJECTIONS = [
    {"candidate_id": f"r{i}", "stage": s, "rejection_category": cat}
    for i, (s, cat) in enumerate([
        ("Phone Screen", "skills_mismatch"), ("Technical Interview", "technical_skills"),
        ("Phone Screen", "skills_mismatch"), ("Technical Interview", "cultural_fit"),
        ("Offer", "compensation"), ("Phone Screen", "experience_level"),
        ("Technical Interview", "technical_skills"), ("Phone Screen", "skills_mismatch"),
        ("Offer", "compensation"), ("Technical Interview", "technical_skills"),
    ])
]

INTERVIEWERS = [
    {"interviewer_id": f"i{i}", "name": name, "interviews_assigned": count, "avg_rating": rating}
    for i, (name, count, rating) in enumerate([
        ("Alice", 18, 4.5), ("Bob", 7, 4.2), ("Carol", 22, 3.8),
        ("Dave", 4, 4.7), ("Eve", 16, 4.1),
    ])
]

OFFERS = [
    {"candidate_id": f"o{i}", "position": pos, "offered": True,
     "accepted": acc, "decline_reason": dr}
    for i, (pos, acc, dr) in enumerate([
        ("SWE", True, None), ("SWE", False, "compensation too low"),
        ("PM", True, None), ("PM", False, "compensation too low"),
        ("SWE", True, None), ("DS", False, "accepted competing offer"),
        ("DS", True, None), ("SWE", False, "compensation too low"),
    ])
]

ALL_DATA = {
    "stages": STAGES,
    "candidates": CANDIDATES,
    "rejections": REJECTIONS,
    "interviewers": INTERVIEWERS,
    "offers": OFFERS,
}

SCENARIO_DATA: dict[str, dict] = {
    "fix_slow_hiring":       {"stages": STAGES, "candidates": CANDIDATES, "rejections": REJECTIONS},
    "balance_workload":      {"interviewers": INTERVIEWERS, "stages": STAGES},
    "investigate_rejections": {"rejections": REJECTIONS, "candidates": CANDIDATES},
    "executive_metrics":     ALL_DATA,
    "interviewer_feedback":  {"interviewers": INTERVIEWERS},
}


# ── helpers ───────────────────────────────────────────────────────────────────

def header(text: str) -> None:
    print(f"\n{'='*60}\n  {text}\n{'='*60}")

def ok(msg: str) -> None:
    print(f"  [PASS] {msg}")

def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


# ── Level 1: imports + registry + RunState ────────────────────────────────────

def test_level1() -> None:
    header("Level 1 — Imports, registry, RunState (no LLM)")

    # BaseScenario
    from orchestration.scenarios.base_scenario import BaseScenario
    ok("BaseScenario imported")

    # All 5 scenario instances
    from orchestration.scenarios.fix_slow_hiring import FIX_SLOW_HIRING
    from orchestration.scenarios.balance_workload import BALANCE_WORKLOAD
    from orchestration.scenarios.investigate_rejections import INVESTIGATE_REJECTIONS
    from orchestration.scenarios.executive_metrics import EXECUTIVE_METRICS
    from orchestration.scenarios.interviewer_feedback import INTERVIEWER_FEEDBACK

    scenarios = [FIX_SLOW_HIRING, BALANCE_WORKLOAD, INVESTIGATE_REJECTIONS,
                 EXECUTIVE_METRICS, INTERVIEWER_FEEDBACK]
    for s in scenarios:
        assert isinstance(s, BaseScenario), f"{s} is not BaseScenario"
        assert s.name, "scenario has no name"
        assert s.forced_agents, f"{s.name} has empty forced_agents"
    ok(f"All 5 scenario instances valid: {[s.name for s in scenarios]}")

    # build_query / missing_data_keys
    q = FIX_SLOW_HIRING.build_query()
    assert "slow" in q.lower() or "hiring" in q.lower() or "pipeline" in q.lower(), \
        f"Unexpected query: {q[:80]}"
    ok(f"build_query(): '{q[:60]}...'")

    missing = FIX_SLOW_HIRING.missing_data_keys({"stages": []})
    assert "candidates" in missing and "rejections" in missing
    ok(f"missing_data_keys(): {missing}")

    no_missing = FIX_SLOW_HIRING.missing_data_keys(
        {"stages": [], "candidates": [], "rejections": []}
    )
    assert no_missing == []
    ok("missing_data_keys() returns [] when all keys present")

    # RunState
    from orchestration.state.run_state import RunState
    rs = RunState(
        run_id="test-001",
        scenario_name="fix_slow_hiring",
        query="Why is hiring slow?",
        forced_agents=["pipeline_health", "improvement_action"],
    )
    assert rs.status == "running"
    rs.mark_complete(
        status="success",
        agents_run=["pipeline_health", "improvement_action", "evaluation"],
        total_tokens=1500,
        total_latency_ms=4200.0,
    )
    assert rs.status == "success"
    assert rs.total_tokens == 1500
    assert rs.completed_at is not None
    summary = rs.to_summary_dict()
    assert summary["run_id"] == "test-001"
    ok(f"RunState lifecycle: pending -> complete. Summary keys: {sorted(summary)}")

    # HiringAnalysisWorkflow (import + registry only)
    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow
    wf = HiringAnalysisWorkflow()
    names = wf.scenario_names()
    assert len(names) == 5, f"Expected 5 scenarios, got {len(names)}: {names}"
    assert sorted(names) == names, "scenario_names() should be sorted"
    ok(f"scenario_names(): {names}")

    info = wf.scenario_info()
    assert len(info) == 5
    for item in info:
        assert {"name", "description", "agents", "required_data"} <= set(item)
    ok("scenario_info() returns 5 dicts with required keys")

    s = wf.get_scenario("executive_metrics")
    assert s.name == "executive_metrics"
    ok("get_scenario('executive_metrics') works")

    try:
        wf.get_scenario("not_a_real_scenario")
        fail("get_scenario() should raise ValueError for unknown scenario")
    except ValueError:
        ok("get_scenario() raises ValueError for unknown scenario")

    print("\nLevel 1 PASSED")


# ── Level 2: run_scenario() for all 5 scenarios ───────────────────────────────

async def test_level2() -> None:
    header("Level 2 — run_scenario() with real LLM (all 5 scenarios)")

    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow
    wf = HiringAnalysisWorkflow()

    for scenario_name, data in SCENARIO_DATA.items():
        print(f"\n  -- Scenario: {scenario_name} --")
        t0 = time.perf_counter()
        try:
            response = await wf.run_scenario(
                name=scenario_name,
                structured_data=data,
                filters={"department": "Engineering"},
            )
        except Exception as e:
            fail(f"run_scenario('{scenario_name}') raised: {e}")
            return

        elapsed = (time.perf_counter() - t0) * 1000
        assert response.status in ("success", "partial_success", "degraded"), \
            f"Unexpected status: {response.status}"
        assert response.summary, "No summary in response"
        assert len(response.agent_outputs) > 0, "No agent outputs"

        run_agents = [o.agent_name for o in response.agent_outputs if o.status != "skipped"]
        ok(f"status={response.status}, agents={run_agents}, "
           f"tokens={response.total_tokens}, latency={elapsed:.0f}ms")
        print(f"     Summary snippet: {response.summary[:120]}...")

    print("\nLevel 2 PASSED")


# ── Level 3: run() via CoordinatorRequest ─────────────────────────────────────

async def test_level3() -> None:
    header("Level 3 — run() via CoordinatorRequest (free-form + scenario-tagged)")

    from orchestration.workflows.hiring_analysis_workflow import HiringAnalysisWorkflow
    from shared.contracts.coordinator_request import CoordinatorRequest
    wf = HiringAnalysisWorkflow()

    # 3a: scenario-tagged request (forced_agents injected automatically)
    print("\n  -- 3a: scenario-tagged CoordinatorRequest (fix_slow_hiring) --")
    req = CoordinatorRequest(
        query="Why is our hiring so slow?",
        scenario="fix_slow_hiring",
        filters={"department": "Engineering"},
    )
    t0 = time.perf_counter()
    resp = await wf.run(req)
    elapsed = (time.perf_counter() - t0) * 1000
    assert resp.status in ("success", "partial_success", "degraded")
    run_agents = [o.agent_name for o in resp.agent_outputs if o.status != "skipped"]
    ok(f"scenario-tagged: status={resp.status}, agents={run_agents}, {elapsed:.0f}ms")
    print(f"     Summary: {resp.summary[:120]}...")

    # 3b: free-form query (RoutingAgent decides)
    print("\n  -- 3b: free-form CoordinatorRequest (no scenario tag) --")
    req2 = CoordinatorRequest(
        query="Show me the key hiring metrics and where we have bottlenecks.",
        filters={},
    )
    t0 = time.perf_counter()
    resp2 = await wf.run(req2)
    elapsed2 = (time.perf_counter() - t0) * 1000
    assert resp2.status in ("success", "partial_success", "degraded")
    run_agents2 = [o.agent_name for o in resp2.agent_outputs if o.status != "skipped"]
    ok(f"free-form: status={resp2.status}, agents={run_agents2}, {elapsed2:.0f}ms")
    print(f"     Summary: {resp2.summary[:120]}...")

    print("\nLevel 3 PASSED")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Day 11 orchestration tests")
    parser.add_argument("--level", type=int, default=1,
                        help="Test level: 1=import-only, 2=LLM scenarios, 3=full run()")
    args = parser.parse_args()

    test_level1()

    if args.level >= 2:
        asyncio.run(test_level2())

    if args.level >= 3:
        asyncio.run(test_level3())

    print("\n" + "="*60)
    print(f"  All Level {args.level} tests PASSED")
    print("="*60)


if __name__ == "__main__":
    main()
