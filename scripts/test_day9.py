"""
Day 9 smoke test — Improvement Action Agent + 2 MCP Tools.

Run:
    .\run.bat scripts\test_day9.py            # all levels (pure Python only — no LLM, no ChromaDB)
    .\run.bat scripts\test_day9.py --llm      # add Level 3: real LLM call
"""
from __future__ import annotations
import asyncio
import sys

RUN_LLM = "--llm" in sys.argv

# ── Sample data ──────────────────────────────────────────────────────────────────

REJECTIONS = [
    {"candidate_id": "C01", "stage": "technical",    "rejection_category": "technical skills", "role": "Engineer"},
    {"candidate_id": "C02", "stage": "technical",    "rejection_category": "coding test",      "role": "Engineer"},
    {"candidate_id": "C03", "stage": "technical",    "rejection_category": "assessment score",  "role": "Engineer"},
    {"candidate_id": "C04", "stage": "phone_screen", "rejection_category": "cultural fit",      "role": "Manager"},
    {"candidate_id": "C05", "stage": "phone_screen", "rejection_category": "communication",     "role": "Manager"},
    {"candidate_id": "C06", "stage": "offer",        "rejection_category": "salary declined",   "role": "Engineer"},
    {"candidate_id": "C07", "stage": "offer",        "rejection_category": "offer declined",    "role": "Engineer"},
    {"candidate_id": "C08", "stage": "screening",    "rejection_category": "experience level",  "role": "Analyst"},
    {"candidate_id": "C09", "stage": "technical",    "rejection_category": "technical skills",  "role": "Engineer"},
    {"candidate_id": "C10", "stage": "technical",    "rejection_category": "coding test",       "role": "Engineer"},
]
CANDIDATES = [{"candidate_id": f"C{i:02d}"} for i in range(1, 21)]
STRUCTURED_DATA = {"rejections": REJECTIONS, "candidates": CANDIDATES}

# ════════════════════════════════════════════════════════════════════════════════
# Step 1 — rejection_analyser (pure Python)
# ════════════════════════════════════════════════════════════════════════════════

print("Step 1: rejection_analyser ...", flush=True)
from agents.insight.improvement_action.rejection_analyser import detect_top_issues

report = detect_top_issues(STRUCTURED_DATA)
print(f"  total_rejections={report.total_rejections}", flush=True)
print(f"  overall_rejection_rate={report.overall_rejection_rate:.1%}", flush=True)
print(f"  issues detected={len(report.issues)}", flush=True)
for iss in report.issues:
    print(f"    [{iss.severity}] {iss.issue_type}: {iss.affected_count} rejections @ {iss.affected_stages}", flush=True)

assert report.total_rejections == 10
assert report.total_candidates == 20
assert report.issues, "Expected at least one issue"
# slow_assessment (technical) should dominate (5 out of 10)
assert report.issues[0].issue_type == "slow_assessment", f"Expected slow_assessment first, got {report.issues[0].issue_type}"
assert report.issues[0].severity == "high"
print("  rejection_analyser OK", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 2 — MCP tool imports (no ChromaDB call yet)
# ════════════════════════════════════════════════════════════════════════════════

print("\nStep 2: MCP tool imports ...", flush=True)
from mcp_platform.mcp.tools.search_similar_interventions import search_similar_interventions, CaseStudy
from mcp_platform.mcp.tools.fetch_best_practices import fetch_best_practices_by_issue, BestPractice, _normalise_issue_type
from mcp_platform.mcp.mcp_client import MCPClient

print("  imports OK", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 3 — issue normalisation + fallback best practices (no ChromaDB)
# ════════════════════════════════════════════════════════════════════════════════

print("\nStep 3: issue normalisation + built-in fallback ...", flush=True)

cases = [
    ("slow technical assessment stage", "slow_assessment"),
    ("candidates failing coding test",  "slow_assessment"),
    ("high rejection rate at screen",   "high_rejection"),
    ("offer declined salary",           "offer_decline"),
    ("linkedin ghosting candidates",    "sourcing_quality"),
]
for text, expected in cases:
    got = _normalise_issue_type(text)
    assert got == expected, f"Expected {expected!r}, got {got!r} for {text!r}"
    print(f"  '{text[:40]}' -> {got}", flush=True)

async def _test_fallback():
    practices = await fetch_best_practices_by_issue("slow technical assessment")
    assert practices, "Expected at least one fallback practice"
    print(f"  fallback best practices: {len(practices)} returned", flush=True)
    for bp in practices:
        print(f"    {bp.practice_id}: {bp.title}", flush=True)
        assert bp.steps, "Practice must have steps"

asyncio.run(_test_fallback())
print("  fallback best practices OK", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 4 — MCPClient.fetch_evidence (ChromaDB may be down — degrades gracefully)
# ════════════════════════════════════════════════════════════════════════════════

print("\nStep 4: MCPClient.fetch_evidence (ChromaDB optional) ...", flush=True)

async def _test_mcp_client():
    client = MCPClient(timeout_seconds=5)
    case_studies, practices = await client.fetch_evidence(
        "slow technical assessment is causing candidate drop-off",
        role="Software Engineer",
    )
    print(f"  case_studies returned: {len(case_studies)}", flush=True)
    print(f"  best_practices returned: {len(practices)}", flush=True)
    # Must always return at least best practices (fallback)
    assert practices, "fetch_evidence must return at least fallback best practices"

asyncio.run(_test_mcp_client())
print("  MCPClient OK", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 5 — ImprovementActionAgent instantiation + registry
# ════════════════════════════════════════════════════════════════════════════════

print("\nStep 5: ImprovementActionAgent import + registry ...", flush=True)
from agents.insight.improvement_action.improvement_action_agent import ImprovementActionAgent
from agents.coordinator.coordinator_agent import CoordinatorAgent, _AGENT_REGISTRY

agent = ImprovementActionAgent()
print(f"  agent_name={agent.agent_name}, model_tier={agent.model_tier}", flush=True)
assert agent.agent_name == "improvement_action"

# CoordinatorAgent should now pick it up via _load_available_agents
coord = CoordinatorAgent()
print(f"  registry keys: {sorted(_AGENT_REGISTRY.keys())}", flush=True)
assert "improvement_action" in _AGENT_REGISTRY, "ImprovementActionAgent not in registry"
print("  registry OK", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 6 — Optional: full analyse() call with real LLM
# ════════════════════════════════════════════════════════════════════════════════

if RUN_LLM:
    print("\nStep 6: ImprovementActionAgent.analyse() with real LLM ...", flush=True)
    import time
    from agents.base.base_agent import AgentContext

    async def _test_llm():
        context = AgentContext(
            query="What corrective actions should we take to reduce technical stage rejections?",
            run_id="day9-test",
            structured_data=STRUCTURED_DATA,
            rag_collections=[],
        )
        t0 = time.monotonic()
        output = await agent.analyse(context)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"  status={output.status}, confidence={output.confidence_score:.2f}", flush=True)
        print(f"  insights={len(output.insights)}, recommendations={len(output.recommendations)}", flush=True)
        print(f"  latency={elapsed:.0f} ms, tokens={output.token_usage.input_tokens}/{output.token_usage.output_tokens}", flush=True)
        print(f"  MCP case studies used: {output.metadata.get('mcp_case_study_count', 0)}", flush=True)
        for i, ins in enumerate(output.insights, 1):
            print(f"  insight {i}: {ins[:120]}", flush=True)
        assert output.status == "success", f"Expected success, got: {output.metadata}"
        assert output.insights

    asyncio.run(_test_llm())
    print("  LLM call OK", flush=True)
else:
    print("\nStep 6: skipped (pass --llm to run LLM integration test)", flush=True)

print("\nAll Day 9 checks passed.", flush=True)
