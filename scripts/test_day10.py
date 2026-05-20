"""
Day 10 smoke test — ResourceOptimization + OfferInsights + Evaluation + Optimization.

Run:
    .\run.bat scripts\test_day10.py           # pure Python + imports (no LLM)
    .\run.bat scripts\test_day10.py --llm     # add real LLM calls for all 4 agents
"""
from __future__ import annotations
import asyncio, sys, time

RUN_LLM = "--llm" in sys.argv

# ── Shared sample data ────────────────────────────────────────────────────────────

INTERVIEWERS = [
    {"interviewer_id": "IV01", "name": "Alice",   "interviews_assigned": 22, "avg_hours_per_interview": 1.5, "avg_rating": 4.2},
    {"interviewer_id": "IV02", "name": "Bob",     "interviews_assigned": 18, "avg_hours_per_interview": 1.5, "avg_rating": 3.8},
    {"interviewer_id": "IV03", "name": "Carol",   "interviews_assigned":  2, "avg_hours_per_interview": 1.5, "avg_rating": 4.5},
    {"interviewer_id": "IV04", "name": "Dave",    "interviews_assigned":  9, "avg_hours_per_interview": 1.5, "avg_rating": 4.0},
    {"interviewer_id": "IV05", "name": "Eve",     "interviews_assigned": 16, "avg_hours_per_interview": 2.0, "avg_rating": 3.9},
]

OFFERS = [
    {"candidate_id": "C01", "position": "Software Engineer", "salary_offered": 95000,  "status": "accepted",  "days_to_respond": 3,  "decline_reason": None},
    {"candidate_id": "C02", "position": "Software Engineer", "salary_offered": 90000,  "status": "declined",  "days_to_respond": 5,  "decline_reason": "low salary offer"},
    {"candidate_id": "C03", "position": "Software Engineer", "salary_offered": 88000,  "status": "declined",  "days_to_respond": 2,  "decline_reason": "compensation too low"},
    {"candidate_id": "C04", "position": "Software Engineer", "salary_offered": 92000,  "status": "pending",   "days_to_respond": None, "decline_reason": None},
    {"candidate_id": "C05", "position": "Data Analyst",      "salary_offered": 70000,  "status": "accepted",  "days_to_respond": 4,  "decline_reason": None},
    {"candidate_id": "C06", "position": "Data Analyst",      "salary_offered": 68000,  "status": "accepted",  "days_to_respond": 3,  "decline_reason": None},
    {"candidate_id": "C07", "position": "Data Analyst",      "salary_offered": 65000,  "status": "declined",  "days_to_respond": 6,  "decline_reason": "accepted competitor offer"},
    {"candidate_id": "C08", "position": "Product Manager",   "salary_offered": 110000, "status": "declined",  "days_to_respond": 1,  "decline_reason": "low salary"},
    {"candidate_id": "C09", "position": "Product Manager",   "salary_offered": 115000, "status": "declined",  "days_to_respond": 2,  "decline_reason": "package not competitive"},
    {"candidate_id": "C10", "position": "Product Manager",   "salary_offered": 112000, "status": "declined",  "days_to_respond": 3,  "decline_reason": "salary package"},
]

STRUCTURED_DATA = {"interviewers": INTERVIEWERS, "offers": OFFERS}

# ════════════════════════════════════════════════════════════════════════════════
# Step 1 — workload_calculator
# ════════════════════════════════════════════════════════════════════════════════
print("Step 1: workload_calculator ...", flush=True)
from agents.insight.resource_optimization.workload_calculator import compute_workload

report = compute_workload(STRUCTURED_DATA)
print(report.to_text(), flush=True)
assert report.total_interviewers == 5
assert len(report.overloaded) == 3      # Alice (22), Bob (18), Eve (16) > threshold 15
assert len(report.underutilised) == 1   # Carol (2) < 3
print("  workload_calculator OK\n", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 2 — offer_analyser
# ════════════════════════════════════════════════════════════════════════════════
print("Step 2: offer_analyser ...", flush=True)
from agents.insight.offer_insights.offer_analyser import compute_offer_stats

offer_report = compute_offer_stats(STRUCTURED_DATA)
print(offer_report.to_text(), flush=True)
assert offer_report.total_offers == 10
assert offer_report.overall_acceptance_rate == 0.3   # 3/10
assert "Product Manager" in offer_report.declining_positions
assert offer_report.salary_flags, "Should flag salary-related declines"
print("  offer_analyser OK\n", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 3 — claim_verifier
# ════════════════════════════════════════════════════════════════════════════════
print("Step 3: claim_verifier ...", flush=True)
from agents.support.evaluation.claim_verifier import verify_outputs
from shared.contracts.agent_output import AgentOutput, TokenUsage

# Build synthetic agent outputs to verify
good_output = AgentOutput(
    agent_name="pipeline_health",
    status="success",
    insights=["Technical stage has 70% drop-off rate", "Average time-in-stage is 22 days"],
    recommendations=[],
    evidence=[],
    confidence_score=0.82,
    token_usage=TokenUsage(input_tokens=800, output_tokens=200),
    latency_ms=4500.0,
)
weak_output = AgentOutput(
    agent_name="sourcing_quality",
    status="success",
    insights=[],                    # no insights — should be flagged
    recommendations=[],
    evidence=[],
    confidence_score=0.35,          # low — should be flagged
    token_usage=TokenUsage(input_tokens=400, output_tokens=50),
    latency_ms=2200.0,
)
error_output = AgentOutput(
    agent_name="improvement_action",
    status="error",
    insights=[],
    recommendations=[],
    evidence=[],
    confidence_score=0.0,
    token_usage=TokenUsage(input_tokens=0, output_tokens=0),
    latency_ms=100.0,
    metadata={"error": "ChromaDB unavailable"},
)

summary = verify_outputs([good_output, weak_output, error_output])
print(summary.to_text(), flush=True)
assert summary.total_agents == 3
assert summary.passed == 1             # only good_output passes
assert summary.flagged == 2
assert any(r.agent_name == "pipeline_health" and r.passed for r in summary.results)
print("  claim_verifier OK\n", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 4 — cost_tracker
# ════════════════════════════════════════════════════════════════════════════════
print("Step 4: cost_tracker ...", flush=True)
from agents.support.optimization.cost_tracker import summarise_run_cost

cost_summary = summarise_run_cost([good_output, weak_output, error_output])
print(cost_summary.to_text(), flush=True)
assert cost_summary.total_tokens == (800 + 200 + 400 + 50)   # 1450
assert cost_summary.total_cost_usd > 0
print("  cost_tracker OK\n", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 5 — agent imports + coordinator registry
# ════════════════════════════════════════════════════════════════════════════════
print("Step 5: agent imports + coordinator registry ...", flush=True)
from agents.insight.resource_optimization.resource_optimization_agent import ResourceOptimizationAgent
from agents.insight.offer_insights.offer_insights_agent import OfferInsightsAgent
from agents.support.evaluation.evaluation_agent import EvaluationAgent
from agents.support.optimization.optimization_agent import OptimizationAgent
from agents.coordinator.coordinator_agent import CoordinatorAgent, _AGENT_REGISTRY

coord = CoordinatorAgent()
print(f"  registry: {sorted(_AGENT_REGISTRY.keys())}", flush=True)
for name in ("resource_optimization", "offer_insights", "evaluation", "optimization"):
    assert name in _AGENT_REGISTRY, f"{name} not in registry"
print("  all Day 10 agents registered OK\n", flush=True)

# ════════════════════════════════════════════════════════════════════════════════
# Step 6 — Optional: LLM calls for each agent
# ════════════════════════════════════════════════════════════════════════════════
if not RUN_LLM:
    print("Step 6: skipped (pass --llm to run LLM integration tests)", flush=True)
    print("\nAll Day 10 smoke checks passed.", flush=True)
    sys.exit(0)

print("Step 6: LLM integration tests ...\n", flush=True)
from agents.base.base_agent import AgentContext

AGENTS_TO_TEST = [
    ("ResourceOptimizationAgent", ResourceOptimizationAgent,
     "Which interviewers are overloaded and how should we rebalance the workload?",
     STRUCTURED_DATA),
    ("OfferInsightsAgent", OfferInsightsAgent,
     "Why is our offer acceptance rate low and which positions are most at risk?",
     STRUCTURED_DATA),
]

async def run_insight_agents():
    outputs = []
    for label, AgentClass, query, data in AGENTS_TO_TEST:
        ctx = AgentContext(query=query, run_id="day10-test", structured_data=data, rag_collections=[])
        t0 = time.monotonic()
        out = await AgentClass().analyse(ctx)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"  [{label}]", flush=True)
        print(f"    status={out.status}, confidence={out.confidence_score:.2f}, "
              f"insights={len(out.insights)}, recs={len(out.recommendations)}, "
              f"latency={elapsed:.0f} ms", flush=True)
        for i, ins in enumerate(out.insights[:3], 1):
            print(f"    insight {i}: {ins[:110]}", flush=True)
        assert out.status == "success", f"{label} failed: {out.metadata}"
        outputs.append(out)
    return outputs

insight_outputs = asyncio.run(run_insight_agents())

async def run_support_agents(prev_outputs):
    for label, AgentClass, query in [
        ("EvaluationAgent",   EvaluationAgent,   "Evaluate the quality of the insight agent outputs"),
        ("OptimizationAgent", OptimizationAgent, "How can we reduce cost and latency across agents?"),
    ]:
        ctx = AgentContext(
            query=query, run_id="day10-test",
            structured_data=STRUCTURED_DATA,
            rag_collections=[],
            previous_outputs=prev_outputs,
        )
        t0 = time.monotonic()
        out = await AgentClass().analyse(ctx)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"\n  [{label}]", flush=True)
        print(f"    status={out.status}, confidence={out.confidence_score:.2f}, "
              f"insights={len(out.insights)}, latency={elapsed:.0f} ms", flush=True)
        if label == "EvaluationAgent":
            print(f"    verification: {out.metadata.get('verification')}", flush=True)
        if label == "OptimizationAgent":
            print(f"    cost_summary: {out.metadata.get('cost_summary')}", flush=True)
        for i, ins in enumerate(out.insights[:3], 1):
            print(f"    insight {i}: {ins[:110]}", flush=True)
        assert out.status == "success", f"{label} failed: {out.metadata}"

asyncio.run(run_support_agents(insight_outputs))
print("\nAll Day 10 LLM tests passed.", flush=True)
