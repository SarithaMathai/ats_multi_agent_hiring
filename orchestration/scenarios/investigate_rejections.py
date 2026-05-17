"""
Scenario 3 — Investigate Rejections

User question: "Why are candidates being rejected and is it our sourcing or our process?"

Agents forced:
  improvement_action  — analyses rejection patterns and pulls MCP case studies / best practices
  sourcing_quality    — evaluates which channels produce high-rejection candidates
  evaluation          — cross-checks both outputs for consistency
  optimization        — reports token cost and latency for the run

Required data:
  rejections  — per-candidate rejection records with stage and category
  candidates  — full candidate list with source_channel for channel-level analysis
"""
from orchestration.scenarios.base_scenario import BaseScenario

INVESTIGATE_REJECTIONS = BaseScenario(
    name="investigate_rejections",
    description="Root-cause rejection patterns across stages and sourcing channels",
    default_query=(
        "Why are candidates being rejected? Identify whether rejections cluster at specific "
        "stages or from specific sourcing channels, and recommend targeted fixes for both "
        "the screening process and sourcing strategy."
    ),
    forced_agents=["improvement_action", "sourcing_quality", "evaluation", "optimization"],
    required_data_keys=["rejections", "candidates"],
)
