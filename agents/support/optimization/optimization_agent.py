"""
Optimization Agent — Day 10 (support tier).

Analyses token usage, API latency, and cost metrics across all agent
outputs. Recommends model tier changes, caching opportunities, or prompt
simplifications that would reduce cost without sacrificing output quality.

Runs AFTER all insight agents and the Evaluation agent via LangGraph's
run_support node.

Workflow inside analyse():
  1. summarise_run_cost(context.previous_outputs)  — pure Python cost roll-up
  2. build cost summary text                        — fed into the LLM prompt
  3. _call_llm()                                   — LLM produces recommendations
"""
from __future__ import annotations

from agents.base.base_agent import AgentContext, BaseAgent
from agents.support.optimization.cost_tracker import RunCostSummary, summarise_run_cost
from shared.constants.agent_names import OPTIMIZATION
from shared.contracts.agent_output import AgentOutput


class OptimizationAgent(BaseAgent):
    agent_name = OPTIMIZATION
    model_tier = "support"
    default_collections: list[str] = []   # optimization needs no external RAG

    async def analyse(self, context: AgentContext) -> AgentOutput:
        cost_summary = summarise_run_cost(context.previous_outputs)
        data_summary = _build_summary(cost_summary, context)
        output = await self._call_llm(context, data_summary=data_summary)
        output.metadata["cost_summary"] = {
            "total_tokens": cost_summary.total_tokens,
            "total_cost_usd": round(cost_summary.total_cost_usd, 6),
            "avg_latency_ms": round(cost_summary.avg_latency_ms, 1),
            "p95_latency_ms": round(cost_summary.p95_latency_ms, 1),
            "flagged_agents": cost_summary.flagged_agents,
        }
        return output


def _build_summary(cost_summary: RunCostSummary, context: AgentContext) -> str:
    lines = [cost_summary.to_text()]

    # Add evaluation findings if available — cross-inform optimization decisions
    for prev in context.previous_outputs:
        if prev.agent_name == OPTIMIZATION:
            continue
        if prev.metadata.get("verification"):
            v = prev.metadata["verification"]
            lines.append(
                f"\nEvaluation findings: {v['passed']}/{v['total_agents']} agents passed, "
                f"flagged: {v.get('flagged_agents', [])}"
            )
            break

    lines.append(
        "\nOptimize for: lower cost (fewer tokens), lower latency (faster agents), "
        "or better quality (higher confidence scores). Consider model tier downgrades "
        "for agents producing low-complexity outputs."
    )
    return "\n".join(lines)
