"""
Sourcing Quality Agent — Day 8.

Evaluates which candidate source channels deliver quality hires and flags
channels that produce high volumes but low pass rates, or are under-utilised.

Workflow inside analyse():
  1. compute_channel_stats()    — pure Python, no I/O
  2. build data summary text    — fed into the LLM prompt
  3. _call_llm()                — RAG + prompt + LLM + output parsing
"""
from __future__ import annotations

from agents.base.base_agent import AgentContext, BaseAgent
from agents.insight.sourcing_quality.channel_analyser import compute_channel_stats
from shared.contracts.agent_output import AgentOutput
from shared.constants.agent_names import SOURCING_QUALITY


class SourcingQualityAgent(BaseAgent):
    agent_name = SOURCING_QUALITY
    model_tier = "insight"
    default_collections: list[str] = ["ats_resumes", "ats_candidates"]

    async def analyse(self, context: AgentContext) -> AgentOutput:
        report = compute_channel_stats(context.structured_data)
        data_summary = _build_summary(report, context)
        output = await self._call_llm(context, data_summary=data_summary)
        output.metadata["channel_report"] = {
            "total_candidates": report.total_candidates,
            "total_channels": report.total_channels,
            "top_channel_by_hire_rate": report.top_channel_by_hire_rate,
            "top_channel_by_volume": report.top_channel_by_volume,
            "underperforming_channels": report.underperforming_channels,
            "underutilised_channels": report.underutilised_channels,
        }
        return output


# ── Private helpers ──────────────────────────────────────────────────────────────

def _build_summary(report, context: AgentContext) -> str:
    lines = [report.to_text()]

    # Surface any pipeline_health output if it ran before us
    for prev in context.previous_outputs:
        if prev.agent_name == "pipeline_health" and prev.insights:
            lines.append("\nPipeline Health context (from earlier agent):")
            for insight in prev.insights[:3]:
                lines.append(f"  - {insight}")
            break

    return "\n".join(lines)
