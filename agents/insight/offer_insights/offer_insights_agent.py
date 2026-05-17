"""
Offer Insights Agent — Day 10.

Tracks offer outcomes, acceptance rates, and compensation signals.
Identifies positions with declining acceptance or salary misalignment
and explains likely root causes.

Workflow inside analyse():
  1. compute_offer_stats()   — pure Python, no I/O
  2. build data summary      — fed into the LLM prompt
  3. _call_llm()             — RAG + prompt + LLM + output parsing
"""
from __future__ import annotations

from agents.base.base_agent import AgentContext, BaseAgent
from agents.insight.offer_insights.offer_analyser import compute_offer_stats
from shared.constants.agent_names import OFFER_INSIGHTS
from shared.contracts.agent_output import AgentOutput


class OfferInsightsAgent(BaseAgent):
    agent_name = OFFER_INSIGHTS
    model_tier = "insight"
    default_collections: list[str] = ["ats_candidates"]

    async def analyse(self, context: AgentContext) -> AgentOutput:
        report = compute_offer_stats(context.structured_data)
        data_summary = _build_summary(report, context)
        output = await self._call_llm(context, data_summary=data_summary)
        output.metadata["offer_report"] = {
            "total_offers": report.total_offers,
            "acceptance_rate": round(report.overall_acceptance_rate, 4),
            "avg_days_to_respond": round(report.avg_days_to_respond, 1),
            "declining_positions": report.declining_positions,
            "salary_flags": report.salary_flags,
        }
        return output


def _build_summary(report, context: AgentContext) -> str:
    lines = [report.to_text()]
    for prev in context.previous_outputs:
        if prev.agent_name in ("pipeline_health", "sourcing_quality") and prev.insights:
            lines.append(f"\nContext from {prev.agent_name}:")
            lines.extend(f"  - {i}" for i in prev.insights[:2])
    return "\n".join(lines)
