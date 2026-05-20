"""
Evaluation Agent — Day 10 (support tier).

Reviews all other agents' outputs for internal consistency, evidence
sufficiency, and realistic confidence scores. Flags any claims that
lack supporting data and downgrades confidence where appropriate.

Runs AFTER all insight agents via LangGraph's run_support node.

Workflow inside analyse():
  1. verify_outputs(context.previous_outputs)  — pure Python quality check
  2. build verification summary text            — fed into the LLM prompt
  3. _call_llm()                               — LLM produces final evaluation
"""
from __future__ import annotations

from agents.base.base_agent import AgentContext, BaseAgent
from agents.support.evaluation.claim_verifier import VerificationSummary, verify_outputs
from shared.constants.agent_names import EVALUATION
from shared.contracts.agent_output import AgentOutput


class EvaluationAgent(BaseAgent):
    agent_name = EVALUATION
    model_tier = "support"
    default_collections: list[str] = []   # evaluation needs no external RAG

    async def analyse(self, context: AgentContext) -> AgentOutput:
        summary = verify_outputs(context.previous_outputs)
        data_summary = _build_summary(summary, context)
        output = await self._call_llm(context, data_summary=data_summary)
        output.metadata["verification"] = {
            "total_agents": summary.total_agents,
            "passed": summary.passed,
            "flagged": summary.flagged,
            "flagged_agents": [r.agent_name for r in summary.results if not r.passed],
        }
        return output


def _build_summary(summary: VerificationSummary, context: AgentContext) -> str:
    lines = [summary.to_text()]

    # Inline the insights from each agent so the LLM can cross-check claims
    if context.previous_outputs:
        lines.append("\n--- Insight agent outputs to evaluate ---")
        for prev in context.previous_outputs:
            if prev.agent_name in (EVALUATION,):
                continue   # skip self
            lines.append(f"\n[{prev.agent_name}] confidence={prev.confidence_score:.2f}")
            for ins in prev.insights[:3]:
                lines.append(f"  * {ins[:200]}")
            for rec in prev.recommendations[:2]:
                lines.append(f"  -> [{rec.priority}] {rec.title}")

    return "\n".join(lines)
