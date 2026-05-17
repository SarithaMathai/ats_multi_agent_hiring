"""
Day 9 LLM integration test — Improvement Action Agent + 2 MCP Tools.

Levels tested:
  Level 1 (pure Python)   : rejection_analyser, issue normalisation, fallback practices [no LLM, no ChromaDB]
  Level 2 (MCP + LLM)     : MCPClient.fetch_evidence + ImprovementActionAgent.analyse()
  Level 3 (coordinator)   : Full pipeline via CoordinatorAgent.run_pipeline()
  Level 4 (cross-agent)   : Pipeline Health passes context to Improvement Action

Run:
    .\run.bat scripts\test_day9_llm.py             # Level 1 only
    .\run.bat scripts\test_day9_llm.py --level 2   # up to agent LLM call
    .\run.bat scripts\test_day9_llm.py --level 3   # up to coordinator pipeline
    .\run.bat scripts\test_day9_llm.py --level 4   # cross-agent context test
"""
from __future__ import annotations

import asyncio
import sys
import time

MAX_LEVEL = 1
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--level" and i + 1 < len(sys.argv[1:]):
        MAX_LEVEL = int(sys.argv[i + 2])
        break

print(f"Running Day 9 LLM tests up to Level {MAX_LEVEL}\n", flush=True)

# ── Shared sample data ───────────────────────────────────────────────────────────

REJECTIONS = [
    {"candidate_id": "C01", "stage": "technical",    "rejection_category": "technical skills",  "role": "Software Engineer"},
    {"candidate_id": "C02", "stage": "technical",    "rejection_category": "coding test",       "role": "Software Engineer"},
    {"candidate_id": "C03", "stage": "technical",    "rejection_category": "assessment score",  "role": "Software Engineer"},
    {"candidate_id": "C04", "stage": "technical",    "rejection_category": "technical skills",  "role": "Software Engineer"},
    {"candidate_id": "C05", "stage": "technical",    "rejection_category": "coding test",       "role": "Data Engineer"},
    {"candidate_id": "C06", "stage": "phone_screen", "rejection_category": "cultural fit",      "role": "Manager"},
    {"candidate_id": "C07", "stage": "phone_screen", "rejection_category": "communication",     "role": "Manager"},
    {"candidate_id": "C08", "stage": "phone_screen", "rejection_category": "experience level",  "role": "Analyst"},
    {"candidate_id": "C09", "stage": "offer",        "rejection_category": "salary declined",   "role": "Software Engineer"},
    {"candidate_id": "C10", "stage": "offer",        "rejection_category": "offer declined",    "role": "Software Engineer"},
    {"candidate_id": "C11", "stage": "screening",    "rejection_category": "experience level",  "role": "Analyst"},
    {"candidate_id": "C12", "stage": "technical",    "rejection_category": "coding test",       "role": "Software Engineer"},
]

STAGES = [
    {"stage_name": "screening",    "candidates_entered": 80,  "candidates_exited": 60,  "avg_days_in_stage": 2.0},
    {"stage_name": "phone_screen", "candidates_entered": 60,  "candidates_exited": 35,  "avg_days_in_stage": 5.0},
    {"stage_name": "technical",    "candidates_entered": 35,  "candidates_exited": 10,  "avg_days_in_stage": 18.0},
    {"stage_name": "offer",        "candidates_entered": 10,  "candidates_exited": 6,   "avg_days_in_stage": 4.0},
]

CANDIDATES = [{"candidate_id": f"C{i:02d}", "status": "rejected"} for i in range(1, 21)]

STRUCTURED_DATA = {
    "rejections": REJECTIONS,
    "candidates": CANDIDATES,
    "stages": STAGES,
}

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — Pure Python (no LLM, no ChromaDB)
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 1 — Pure Python (no LLM, no ChromaDB)", flush=True)
print("=" * 60, flush=True)

from agents.insight.improvement_action.rejection_analyser import detect_top_issues
from mcp_platform.mcp.tools.fetch_best_practices import (
    _normalise_issue_type,
    fetch_best_practices_by_issue,
)

# 1a. Rejection analyser
print("\n[rejection_analyser]", flush=True)
report = detect_top_issues(STRUCTURED_DATA)
print(report.to_text(), flush=True)

assert report.total_rejections == 12
assert report.issues, "Expected at least one issue"
assert report.issues[0].issue_type == "slow_assessment"
assert report.issues[0].severity == "high"

# 1b. Issue normalisation
print("\n[issue normalisation]", flush=True)
test_cases = [
    ("slow technical assessment causing drop-off", "slow_assessment"),
    ("candidates failing coding test at technical stage",   "slow_assessment"),
    ("high rejection rate due to poor culture fit",        "high_rejection"),
    ("offer declined due to salary package",               "offer_decline"),
    ("linkedin sourcing quality low",                      "sourcing_quality"),
    ("candidates ghosting after phone screen",             "sourcing_quality"),
]
for text, expected in test_cases:
    got = _normalise_issue_type(text)
    assert got == expected, f"Got {got!r} for {text!r}, expected {expected!r}"
    print(f"  '{text[:45]}' -> {got}", flush=True)

# 1c. Fallback best practices (no ChromaDB needed)
print("\n[fallback best practices]", flush=True)

async def _level1_fallback():
    for issue_text in ["slow assessment", "high rejection", "offer declined", "sourcing"]:
        practices = await fetch_best_practices_by_issue(issue_text)
        assert practices, f"No fallback for {issue_text!r}"
        bp = practices[0]
        print(f"  '{issue_text}' -> {bp.practice_id}: {bp.title} ({len(bp.steps)} steps)", flush=True)
        assert bp.steps

asyncio.run(_level1_fallback())

print("\nLevel 1 PASSED\n", flush=True)

if MAX_LEVEL < 2:
    sys.exit(0)

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — MCP tools + Agent LLM call (real OpenAI)
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 2 — MCP tools + Agent LLM integration", flush=True)
print("=" * 60, flush=True)

from agents.base.base_agent import AgentContext
from agents.insight.improvement_action.improvement_action_agent import ImprovementActionAgent
from mcp_platform.mcp.mcp_client import MCPClient


async def run_level2():
    # 2a. MCPClient.fetch_evidence — both tools concurrently
    print("\n-- MCPClient.fetch_evidence() --", flush=True)
    client = MCPClient(timeout_seconds=10)
    t0 = time.monotonic()
    case_studies, practices = await client.fetch_evidence(
        issue="slow technical assessment causing high engineer rejection rate",
        role="Software Engineer",
    )
    elapsed = (time.monotonic() - t0) * 1000
    print(f"  case_studies : {len(case_studies)} returned in {elapsed:.0f} ms", flush=True)
    print(f"  best_practices: {len(practices)} returned", flush=True)
    for cs in case_studies[:3]:
        print(f"    case study: [{cs.case_study_id}] {cs.issue_type} | "
              f"impact={cs.observed_impact_pct:.0f}% | {cs.implementation_weeks}w", flush=True)
    for bp in practices[:2]:
        print(f"    practice: [{bp.practice_id}] {bp.title} ({len(bp.steps)} steps)", flush=True)
    assert practices, "Must always return at least fallback practices"

    # 2b. ImprovementActionAgent.analyse() — full flow
    print("\n-- ImprovementActionAgent.analyse() --", flush=True)
    context = AgentContext(
        query="What corrective actions should we take to reduce technical-stage rejections for Software Engineers?",
        run_id="day9-llm-test",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],      # skip RAG retriever — ChromaDB not needed here
        filters={"role": "Software Engineer"},
    )
    t0 = time.monotonic()
    agent = ImprovementActionAgent()
    output = await agent.analyse(context)
    elapsed = (time.monotonic() - t0) * 1000

    print(f"  status          : {output.status}", flush=True)
    print(f"  confidence      : {output.confidence_score:.2f}", flush=True)
    print(f"  insights        : {len(output.insights)}", flush=True)
    print(f"  recommendations : {len(output.recommendations)}", flush=True)
    print(f"  latency         : {elapsed:.0f} ms", flush=True)
    print(f"  tokens in/out   : {output.token_usage.input_tokens}/{output.token_usage.output_tokens}", flush=True)
    print(f"  MCP case studies: {output.metadata.get('mcp_case_study_count', 0)}", flush=True)
    print(f"  top issue       : {output.metadata['rejection_report']['top_issues'][0]}", flush=True)

    print("\n  Insights:", flush=True)
    for i, ins in enumerate(output.insights, 1):
        print(f"    {i}. {ins[:130]}", flush=True)

    print("\n  Recommendations:", flush=True)
    for rec in output.recommendations:
        print(f"    [{rec.priority}/{rec.effort}] {rec.title}", flush=True)
        print(f"      {rec.description[:100]}", flush=True)

    assert output.status == "success", f"Expected success, got {output.status}: {output.metadata}"
    assert output.insights, "No insights returned"
    assert output.recommendations, "No recommendations returned"
    assert output.confidence_score > 0

    print("\nLevel 2 PASSED\n", flush=True)
    return output


ia_output = asyncio.run(run_level2())

if MAX_LEVEL < 3:
    sys.exit(0)

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — End-to-end via CoordinatorAgent pipeline
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 3 — Full Coordinator pipeline (route -> insights -> support)", flush=True)
print("=" * 60, flush=True)

from agents.coordinator.coordinator_agent import CoordinatorAgent, PipelineRequest


async def run_level3():
    request = PipelineRequest(
        query="Why are so many Software Engineers being rejected at the technical stage, "
              "and what should we do about it?",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],
        run_id="day9-e2e",
    )

    t0 = time.monotonic()
    coord = CoordinatorAgent()
    response = await coord.run_pipeline(request)
    elapsed = (time.monotonic() - t0) * 1000

    print(f"\n  run_id          : {response.run_id}", flush=True)
    print(f"  status          : {response.status}", flush=True)
    print(f"  agents ran      : {[o.agent_name for o in response.agent_outputs]}", flush=True)
    print(f"  total tokens    : {response.total_tokens}", flush=True)
    print(f"  total latency   : {elapsed:.0f} ms", flush=True)
    print(f"  recommendations : {len(response.all_recommendations)}", flush=True)
    print(f"\n  Summary:\n{response.summary}", flush=True)

    assert response.status in ("success", "partial"), f"Unexpected status: {response.status}"
    agent_names = [o.agent_name for o in response.agent_outputs]
    assert "improvement_action" in agent_names, \
        f"ImprovementActionAgent not in pipeline. Got: {agent_names}"

    print("\nLevel 3 PASSED\n", flush=True)
    return response


asyncio.run(run_level3())

if MAX_LEVEL < 4:
    sys.exit(0)

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 4 — Cross-agent context: PipelineHealth -> ImprovementAction
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 4 — Cross-agent: PipelineHealth passes context to ImprovementAction", flush=True)
print("=" * 60, flush=True)

from agents.insight.pipeline_health.pipeline_health_agent import PipelineHealthAgent


async def run_level4():
    # Step A — run PipelineHealthAgent first
    ph_context = AgentContext(
        query="Where are the biggest bottlenecks in the hiring funnel?",
        run_id="day9-cross",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],
    )
    print("\n-- Step A: PipelineHealthAgent --", flush=True)
    ph_output = await PipelineHealthAgent().analyse(ph_context)
    print(f"  status={ph_output.status}, insights={len(ph_output.insights)}", flush=True)
    assert ph_output.status == "success"

    # Step B — ImprovementActionAgent receives PipelineHealth output as previous_outputs
    ia_context = AgentContext(
        query="Given the pipeline bottlenecks, what improvement actions should we take?",
        run_id="day9-cross",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],
        previous_outputs=[ph_output],   # cross-agent context injection
    )
    print("\n-- Step B: ImprovementActionAgent with pipeline health context --", flush=True)
    t0 = time.monotonic()
    ia_output = await ImprovementActionAgent().analyse(ia_context)
    elapsed = (time.monotonic() - t0) * 1000
    print(f"  status={ia_output.status}, insights={len(ia_output.insights)}", flush=True)
    print(f"  latency={elapsed:.0f} ms, tokens={ia_output.token_usage.input_tokens}/{ia_output.token_usage.output_tokens}", flush=True)
    print(f"  MCP case studies: {ia_output.metadata.get('mcp_case_study_count', 0)}", flush=True)
    print("\n  Cross-agent insights:", flush=True)
    for i, ins in enumerate(ia_output.insights, 1):
        print(f"    {i}. {ins[:130]}", flush=True)

    assert ia_output.status == "success"
    assert ia_output.insights

    print("\nLevel 4 PASSED\n", flush=True)


asyncio.run(run_level4())

print("All Day 9 LLM tests passed.", flush=True)
