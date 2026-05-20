"""
Resource Optimization Agent — Day 10.

Analyses interviewer workload distribution. Flags panellists who are
over-capacity, identifies scheduling gaps, and recommends rebalancing
to protect both candidate quality and interviewer wellbeing.

Workflow inside analyse():
  1. compute_workload()      — pure Python, no I/O
  2. build data summary      — fed into the LLM prompt
  3. _call_llm()             — RAG + prompt + LLM + output parsing
"""
from __future__ import annotations

from agents.base.base_agent import AgentContext, BaseAgent
from agents.insight.resource_optimization.workload_calculator import compute_workload
from shared.constants.agent_names import RESOURCE_OPTIMIZATION
from shared.contracts.agent_output import AgentOutput


class ResourceOptimizationAgent(BaseAgent):
    agent_name = RESOURCE_OPTIMIZATION
    model_tier = "insight"
    default_collections: list[str] = ["ats_feedback"]

    async def analyse(self, context: AgentContext) -> AgentOutput:
        report = compute_workload(context.structured_data)
        data_summary = _build_summary(report, context)
        output = await self._call_llm(context, data_summary=data_summary)
        output.metadata["workload_report"] = {
            "total_interviewers": report.total_interviewers,
            "avg_interviews": round(report.avg_interviews_per_interviewer, 1),
            "overloaded_count": len(report.overloaded),
            "underutilised_count": len(report.underutilised),
            "overloaded_names": [iv.name for iv in report.overloaded],
        }
        return output


def _build_summary(report, context: AgentContext) -> str:
    lines = [report.to_text()]
    for prev in context.previous_outputs:
        if prev.agent_name == "pipeline_health" and prev.insights:
            lines.append("\nPipeline Health context:")
            lines.extend(f"  - {i}" for i in prev.insights[:2])
            break
    return "\n".join(lines)
