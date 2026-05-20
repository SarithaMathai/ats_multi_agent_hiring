"""
Day 8 LLM integration test — Pipeline Health + Sourcing Quality agents.

Levels tested:
  Level 1 (pure Python)  : metrics_calculator + channel_analyser            [no LLM]
  Level 2 (agent LLM)    : PipelineHealthAgent.analyse() + SourcingQualityAgent.analyse()
  Level 3 (coordinator)  : Full pipeline via CoordinatorAgent.run_pipeline()

Run:
    .\run.bat scripts\test_day8_llm.py
    .\run.bat scripts\test_day8_llm.py --level 2   # skip coordinator (faster)
    .\run.bat scripts\test_day8_llm.py --level 1   # pure Python only (no API calls)
"""
from __future__ import annotations

import asyncio
import sys
import time

# ── Parse --level flag ───────────────────────────────────────────────────────────
MAX_LEVEL = 3
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--level" and i + 1 < len(sys.argv[1:]):
        MAX_LEVEL = int(sys.argv[i + 2])
        break

print(f"Running Day 8 LLM tests up to Level {MAX_LEVEL}\n", flush=True)

# ── Shared sample data ───────────────────────────────────────────────────────────

STAGES_DATA = [
    {"stage_name": "screening",    "candidates_entered": 200, "candidates_exited": 120, "avg_days_in_stage": 2.5},
    {"stage_name": "phone_screen", "candidates_entered": 120, "candidates_exited": 55,  "avg_days_in_stage": 7.2},
    {"stage_name": "interview",    "candidates_entered": 55,  "candidates_exited": 18,  "avg_days_in_stage": 22.0},
    {"stage_name": "offer",        "candidates_entered": 18,  "candidates_exited": 12,  "avg_days_in_stage": 6.0},
]
CANDIDATES_DATA = [
    {"candidate_id": "C001", "current_stage": "interview",    "days_in_current_stage": 30, "status": "active",
     "source_channel": "LinkedIn", "quality_score": 0.82},
    {"candidate_id": "C002", "current_stage": "phone_screen", "days_in_current_stage": 5,  "status": "active",
     "source_channel": "Referral", "quality_score": 0.90},
    {"candidate_id": "C003", "current_stage": "offer",        "days_in_current_stage": 3,  "status": "offer",
     "source_channel": "Indeed",   "quality_score": 0.65},
    {"candidate_id": "C004", "current_stage": "interview",    "days_in_current_stage": 18, "status": "active",
     "source_channel": "LinkedIn", "quality_score": 0.75},
    {"candidate_id": "C005", "current_stage": "screening",    "days_in_current_stage": 1,  "status": "active",
     "source_channel": "Referral", "quality_score": 0.88},
    {"candidate_id": "C006", "current_stage": "phone_screen", "days_in_current_stage": 4,  "status": "rejected",
     "source_channel": "Indeed",   "quality_score": 0.40},
    {"candidate_id": "C007", "current_stage": "offer",        "days_in_current_stage": 2,  "status": "hired",
     "source_channel": "Referral", "quality_score": 0.95},
    {"candidate_id": "C008", "current_stage": "interview",    "days_in_current_stage": 25, "status": "active",
     "source_channel": "LinkedIn", "quality_score": 0.70},
]

STRUCTURED_DATA = {"stages": STAGES_DATA, "candidates": CANDIDATES_DATA}

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — Pure Python (no network)
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 1 — Pure Python metrics (no LLM)", flush=True)
print("=" * 60, flush=True)

from agents.insight.pipeline_health.metrics_calculator import compute_pipeline_metrics
from agents.insight.sourcing_quality.channel_analyser import compute_channel_stats

metrics = compute_pipeline_metrics(STRUCTURED_DATA)
print("\n[PipelineMetrics]", flush=True)
print(metrics.to_text(), flush=True)

report = compute_channel_stats(STRUCTURED_DATA)
print("\n[ChannelReport]", flush=True)
print(report.to_text(), flush=True)

print("\nLevel 1 PASSED\n", flush=True)

if MAX_LEVEL < 2:
    sys.exit(0)

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — Agent analyse() with real LLM call
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 2 — Agent LLM integration (real OpenAI call)", flush=True)
print("=" * 60, flush=True)

from agents.base.base_agent import AgentContext
from agents.insight.pipeline_health.pipeline_health_agent import PipelineHealthAgent
from agents.insight.sourcing_quality.sourcing_quality_agent import SourcingQualityAgent


async def run_level2() -> None:
    context = AgentContext(
        query="Identify hiring funnel bottlenecks and evaluate source channel quality.",
        run_id="day8-test",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],   # skip RAG — ChromaDB not running in test env
    )

    print("\n-- PipelineHealthAgent.analyse() --", flush=True)
    t0 = time.monotonic()
    ph_agent = PipelineHealthAgent()
    ph_output = await ph_agent.analyse(context)
    elapsed = (time.monotonic() - t0) * 1000
    print(f"  status         : {ph_output.status}", flush=True)
    print(f"  confidence     : {ph_output.confidence_score:.2f}", flush=True)
    print(f"  insights       : {len(ph_output.insights)}", flush=True)
    print(f"  recommendations: {len(ph_output.recommendations)}", flush=True)
    print(f"  latency        : {elapsed:.0f} ms", flush=True)
    print(f"  tokens (in/out): {ph_output.token_usage.input_tokens}/{ph_output.token_usage.output_tokens}", flush=True)
    print(f"  bottleneck meta: {ph_output.metadata.get('pipeline_metrics', {}).get('bottleneck_stages')}", flush=True)
    for i, ins in enumerate(ph_output.insights, 1):
        print(f"  insight {i}: {ins[:120]}", flush=True)

    assert ph_output.status == "success", f"Expected success, got {ph_output.status}: {ph_output.metadata}"
    assert ph_output.insights, "No insights returned"

    print("\n-- SourcingQualityAgent.analyse() --", flush=True)
    # Pass pipeline_health output as previous — tests the cross-agent context surfacing
    context_with_prev = AgentContext(
        query="Which sourcing channels produce the best-quality hires?",
        run_id="day8-test",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],
        previous_outputs=[ph_output],
    )
    t0 = time.monotonic()
    sq_agent = SourcingQualityAgent()
    sq_output = await sq_agent.analyse(context_with_prev)
    elapsed = (time.monotonic() - t0) * 1000
    print(f"  status         : {sq_output.status}", flush=True)
    print(f"  confidence     : {sq_output.confidence_score:.2f}", flush=True)
    print(f"  insights       : {len(sq_output.insights)}", flush=True)
    print(f"  recommendations: {len(sq_output.recommendations)}", flush=True)
    print(f"  latency        : {elapsed:.0f} ms", flush=True)
    print(f"  tokens (in/out): {sq_output.token_usage.input_tokens}/{sq_output.token_usage.output_tokens}", flush=True)
    print(f"  top channel    : {sq_output.metadata.get('channel_report', {}).get('top_channel_by_hire_rate')}", flush=True)
    for i, ins in enumerate(sq_output.insights, 1):
        print(f"  insight {i}: {ins[:120]}", flush=True)

    assert sq_output.status == "success", f"Expected success, got {sq_output.status}: {sq_output.metadata}"
    assert sq_output.insights, "No insights returned"

    print("\nLevel 2 PASSED\n", flush=True)
    return ph_output, sq_output


ph_out, sq_out = asyncio.run(run_level2())

if MAX_LEVEL < 3:
    sys.exit(0)

# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — End-to-end via CoordinatorAgent pipeline
# ════════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("LEVEL 3 — Full Coordinator pipeline (route → insights → support)", flush=True)
print("=" * 60, flush=True)

from agents.coordinator.coordinator_agent import CoordinatorAgent, PipelineRequest


async def run_level3() -> None:
    request = PipelineRequest(
        query="Give me a full sourcing and pipeline health analysis.",
        structured_data=STRUCTURED_DATA,
        rag_collections=[],
        run_id="day8-e2e",
    )

    t0 = time.monotonic()
    coord = CoordinatorAgent()
    response = await coord.run_pipeline(request)
    elapsed = (time.monotonic() - t0) * 1000

    print(f"\n  run_id         : {response.run_id}", flush=True)
    print(f"  status         : {response.status}", flush=True)
    print(f"  agents ran     : {[o.agent_name for o in response.agent_outputs]}", flush=True)
    print(f"  total tokens   : {response.total_tokens}", flush=True)
    print(f"  total latency  : {elapsed:.0f} ms", flush=True)
    print(f"  recommendations: {len(response.all_recommendations)}", flush=True)
    print(f"\n  Summary:\n{response.summary}", flush=True)

    assert response.status in ("success", "partial"), f"Unexpected status: {response.status}"
    agent_names = [o.agent_name for o in response.agent_outputs]
    assert "pipeline_health" in agent_names or "sourcing_quality" in agent_names, \
        "Neither Day 8 agent appeared in pipeline output"

    print("\nLevel 3 PASSED\n", flush=True)


asyncio.run(run_level3())
print("All Day 8 LLM tests passed.", flush=True)
