"""
Pipeline Health Agent — Day 8.

Diagnoses bottlenecks, stage drop-offs, and stuck candidates in the hiring funnel.

Workflow inside analyse():
  1. compute_pipeline_metrics()   — pure Python, no I/O
  2. build data summary text      — fed into the LLM prompt
  3. _call_llm()                  — RAG + prompt + LLM + output parsing
"""
from __future__ import annotations

from agents.base.base_agent import AgentContext, BaseAgent
from agents.insight.pipeline_health.metrics_calculator import compute_pipeline_metrics
from shared.contracts.agent_output import AgentOutput
from shared.constants.agent_names import PIPELINE_HEALTH


class PipelineHealthAgent(BaseAgent):
    agent_name = PIPELINE_HEALTH
    model_tier = "insight"
    default_collections: list[str] = ["ats_feedback"]

    # Coordinator registers this class so it can be auto-discovered.
    # (Registration happens via CoordinatorAgent.register() in coordinator_agent.py.)

    async def analyse(self, context: AgentContext) -> AgentOutput:
        metrics = compute_pipeline_metrics(context.structured_data)
        data_summary = _build_summary(metrics, context)
        output = await self._call_llm(context, data_summary=data_summary)
        output.metadata["pipeline_metrics"] = {
            "total_candidates": metrics.total_candidates,
            "overall_conversion_rate": round(metrics.overall_conversion_rate, 4),
            "avg_total_pipeline_days": round(metrics.avg_total_pipeline_days, 1),
            "bottleneck_stages": metrics.bottleneck_stages,
            "stuck_candidate_count": len(metrics.stuck_candidates),
        }
        return output


# ── Private helpers ──────────────────────────────────────────────────────────────

def _build_summary(metrics, context: AgentContext) -> str:
    lines = [metrics.to_text()]

    prev_insights: list[str] = []
    for prev in context.previous_outputs:
        if prev.agent_name == "routing" and prev.insights:
            prev_insights = prev.insights[:2]
    if prev_insights:
        lines.append("\nRouting context:")
        lines.extend(f"  - {i}" for i in prev_insights)

    return "\n".join(lines)
