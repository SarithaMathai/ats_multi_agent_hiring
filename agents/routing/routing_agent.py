"""
Routing Agent — decides which insight agents to invoke.

Selection priority (first match wins):
  1. Explicit scenario keyword in query  -> agents_for_scenario()
  2. LLM classification of the query    -> validate_and_filter(LLM output)
  3. Fallback                           -> default_agents() (all five insight agents)

The selected agent list is written into output.metadata["selected_agents"]
so the Coordinator can read it without parsing free-form text.
"""
from __future__ import annotations

import json
import logging

from agents.base.base_agent import AgentContext, BaseAgent
from agents.base.llm_client import LLMClient
from agents.routing.agent_selector import (
    VALID_SCENARIOS,
    agents_for_scenario,
    default_agents,
    validate_and_filter,
)
from shared.contracts.agent_output import AgentOutput, TokenUsage

logger = logging.getLogger(__name__)

# ── Routing prompt ──────────────────────────────────────────────────────────────

_ROUTING_SYSTEM = """\
You are a routing agent for an AI-powered Applicant Tracking System (ATS).
Your ONLY job is to classify the recruiter's query into exactly one scenario
and return the most relevant specialist agents to invoke.

Available scenarios and their typical queries:
  pipeline_health      — bottlenecks, stage conversion, time-to-hire, drop-off rates
  sourcing_quality     — channel effectiveness, source diversity, cost-per-hire, reach
  process_improvement  — rejection patterns, bias detection, process redesign
  resource_optimization — interviewer load, scheduling efficiency, capacity planning
  offer_analysis       — offer acceptance, compensation benchmarking, decline reasons
  full_analysis        — general, broad, or unclassified hiring questions

Available specialist agents:
  pipeline_health, sourcing_quality, improvement_action,
  resource_optimization, offer_insights

Respond with ONLY valid JSON — no markdown, no prose:
{
  "scenario": "<one of the six scenario names>",
  "selected_agents": ["<agent_name>", ...],
  "reasoning": "<one sentence>"
}
"""


# ── Agent class ─────────────────────────────────────────────────────────────────

class RoutingAgent(BaseAgent):
    agent_name  = "routing"
    model_tier  = "support"

    def __init__(self) -> None:
        # Use a dedicated LLM client — routing does not use the generic prompt_builder
        self._llm = LLMClient(tier=self.model_tier)
        self._retriever = None  # routing never does RAG

    async def analyse(self, context: AgentContext) -> AgentOutput:
        query_lower = context.query.lower()

        # ── Priority 1: scenario keyword in query ───────────────────────────────
        for scenario in VALID_SCENARIOS:
            keyword = scenario.replace("_", " ")
            if keyword in query_lower or scenario in query_lower:
                selected = agents_for_scenario(scenario)
                return self._make_output(
                    selected_agents=selected,
                    scenario=scenario,
                    reasoning="Matched scenario keyword in query.",
                )

        # ── Priority 2: LLM classification ─────────────────────────────────────
        try:
            resp = await self._llm.complete(
                system=_ROUTING_SYSTEM,
                messages=[{"role": "user", "content": context.query}],
                max_tokens=256,
                temperature=0.0,
                json_mode=True,
            )
            parsed = json.loads(resp.content)
            scenario = parsed.get("scenario", "full_analysis")
            llm_agents: list[str] = parsed.get("selected_agents", [])

            if scenario in VALID_SCENARIOS:
                selected = agents_for_scenario(scenario)
            elif llm_agents:
                selected = validate_and_filter(llm_agents)
            else:
                selected = default_agents()

            return self._make_output(
                selected_agents=selected,
                scenario=scenario,
                reasoning=parsed.get("reasoning", "LLM classification."),
                token_usage=TokenUsage(
                    input_tokens=resp.token_usage.input_tokens,
                    output_tokens=resp.token_usage.output_tokens,
                ),
                latency_ms=resp.latency_ms,
            )

        except Exception as exc:
            logger.warning("Routing LLM call failed (%s) — using default agents.", exc)

        # ── Priority 3: fallback ────────────────────────────────────────────────
        return self._make_output(
            selected_agents=default_agents(),
            scenario="full_analysis",
            reasoning="Fallback — LLM routing unavailable.",
        )

    # ── Helper ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_output(
        selected_agents: list[str],
        scenario: str,
        reasoning: str,
        token_usage: TokenUsage | None = None,
        latency_ms: float = 0.0,
    ) -> AgentOutput:
        return AgentOutput(
            agent_name="routing",
            status="success",
            insights=[
                f"Scenario: {scenario}",
                f"Agents selected: {', '.join(selected_agents)}",
                reasoning,
            ],
            recommendations=[],
            evidence=[],
            confidence_score=1.0,
            token_usage=token_usage or TokenUsage(input_tokens=0, output_tokens=0),
            latency_ms=latency_ms,
            metadata={
                "selected_agents": selected_agents,
                "scenario": scenario,
            },
        )
