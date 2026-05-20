"""
Day 8 verification — Pipeline Health Agent + Sourcing Quality Agent.

Tests:
  1. metrics_calculator   — pure Python, no network
  2. channel_analyser     — pure Python, no network
  3. Agent class imports  — no heavy packages loaded
  4. CoordinatorAgent     — both agents appear in registry
"""
import sys

print("Step 1: metrics_calculator ...", flush=True)
from agents.insight.pipeline_health.metrics_calculator import compute_pipeline_metrics

sample_stages = [
    {"stage_name": "screening",    "candidates_entered": 100, "candidates_exited": 60,  "avg_days_in_stage": 2.0},
    {"stage_name": "phone_screen", "candidates_entered": 60,  "candidates_exited": 30,  "avg_days_in_stage": 6.5},
    {"stage_name": "interview",    "candidates_entered": 30,  "candidates_exited": 10,  "avg_days_in_stage": 20.0},
    {"stage_name": "offer",        "candidates_entered": 10,  "candidates_exited": 7,   "avg_days_in_stage": 5.0},
]
sample_candidates = [
    {"candidate_id": "C001", "current_stage": "interview", "days_in_current_stage": 25, "status": "active"},
    {"candidate_id": "C002", "current_stage": "phone_screen", "days_in_current_stage": 10, "status": "active"},
    {"candidate_id": "C003", "current_stage": "offer", "days_in_current_stage": 3, "status": "offer"},
]
metrics = compute_pipeline_metrics({"stages": sample_stages, "candidates": sample_candidates})
print(f"  total_candidates={metrics.total_candidates}", flush=True)
print(f"  overall_conversion={metrics.overall_conversion_rate:.1%}", flush=True)
print(f"  bottlenecks={metrics.bottleneck_stages}", flush=True)
print(f"  stuck_candidates={len(metrics.stuck_candidates)}", flush=True)
assert metrics.total_candidates == 100
assert metrics.bottleneck_stages, "Expected at least one bottleneck"
assert len(metrics.stuck_candidates) == 1   # C001 is overdue
print("  metrics_calculator OK", flush=True)

print("\nStep 2: channel_analyser ...", flush=True)
from agents.insight.sourcing_quality.channel_analyser import compute_channel_stats

sample_candidates_sourcing = [
    {"candidate_id": "C1", "source_channel": "LinkedIn",  "status": "hired",    "quality_score": 0.85},
    {"candidate_id": "C2", "source_channel": "LinkedIn",  "status": "rejected", "quality_score": 0.40},
    {"candidate_id": "C3", "source_channel": "LinkedIn",  "status": "active",   "quality_score": 0.72},
    {"candidate_id": "C4", "source_channel": "Referral",  "status": "hired",    "quality_score": 0.90},
    {"candidate_id": "C5", "source_channel": "Referral",  "status": "hired",    "quality_score": 0.88},
    {"candidate_id": "C6", "source_channel": "Indeed",    "status": "rejected", "quality_score": 0.30},
    {"candidate_id": "C7", "source_channel": "Indeed",    "status": "rejected", "quality_score": 0.25},
    {"candidate_id": "C8", "source_channel": "Indeed",    "status": "active",   "quality_score": 0.50},
]
report = compute_channel_stats({"candidates": sample_candidates_sourcing})
print(f"  total_candidates={report.total_candidates}", flush=True)
print(f"  total_channels={report.total_channels}", flush=True)
print(f"  top_by_hire_rate={report.top_channel_by_hire_rate}", flush=True)
print(f"  underperforming={report.underperforming_channels}", flush=True)
assert report.total_candidates == 8
assert report.total_channels == 3
assert report.top_channel_by_hire_rate == "referral"
print("  channel_analyser OK", flush=True)

print("\nStep 3: agent class imports ...", flush=True)
from agents.insight.pipeline_health.pipeline_health_agent import PipelineHealthAgent
from agents.insight.sourcing_quality.sourcing_quality_agent import SourcingQualityAgent

ph = PipelineHealthAgent()
sq = SourcingQualityAgent()
print(f"  PipelineHealthAgent: name={ph.agent_name}, tier={ph.model_tier}, collections={ph.default_collections}", flush=True)
print(f"  SourcingQualityAgent: name={sq.agent_name}, tier={sq.model_tier}, collections={sq.default_collections}", flush=True)
assert ph.agent_name == "pipeline_health"
assert sq.agent_name == "sourcing_quality"
assert ph.model_tier == "insight"
assert sq.model_tier == "insight"
print("  agent imports OK", flush=True)

print("\nStep 4: CoordinatorAgent registry ...", flush=True)
from agents.coordinator.coordinator_agent import CoordinatorAgent, _AGENT_REGISTRY

coord = CoordinatorAgent()
print(f"  registry keys: {sorted(_AGENT_REGISTRY.keys())}", flush=True)
assert "pipeline_health" in _AGENT_REGISTRY, "PipelineHealthAgent not registered"
assert "sourcing_quality" in _AGENT_REGISTRY, "SourcingQualityAgent not registered"
print("  registry OK", flush=True)

print("\nAll Day 8 checks passed.", flush=True)
