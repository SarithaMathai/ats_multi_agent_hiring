"""
Scenario 4 — Executive Metrics

User question: "Give me a complete hiring health report across all dimensions."

Agents forced:  ALL insight agents + both support agents
  pipeline_health       — funnel conversion and time-in-stage
  sourcing_quality      — channel quality and hire rates
  improvement_action    — rejection root causes and corrective actions
  resource_optimization — interviewer workload balance
  offer_insights        — offer acceptance rates and salary signals
  evaluation            — cross-agent quality verification
  optimization          — cost and latency roll-up

Required data:  all structured data keys (uses whatever is provided)
"""
from agents.routing.agent_selector import ALL_INSIGHT_AGENTS, SUPPORT_AGENTS
from orchestration.scenarios.base_scenario import BaseScenario

EXECUTIVE_METRICS = BaseScenario(
    name="executive_metrics",
    description="Full hiring health report across all dimensions",
    default_query=(
        "Provide a comprehensive hiring analytics report covering: pipeline health and "
        "bottlenecks, sourcing channel quality, rejection root causes, interviewer workload, "
        "and offer acceptance rates. Highlight the top 3 issues requiring immediate action."
    ),
    forced_agents=ALL_INSIGHT_AGENTS + SUPPORT_AGENTS,
    required_data_keys=["stages", "candidates", "rejections", "interviewers", "offers"],
)
