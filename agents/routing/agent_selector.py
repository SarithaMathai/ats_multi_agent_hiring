"""
Scenario -> agent mapping for the Routing layer.

The five named scenarios correspond to the five families of hiring questions
recruiters typically ask.  The Routing agent picks the matching scenario;
this module translates that to the ordered list of agents to invoke.

Evaluation and Optimization are always appended as the final two agents
so every pipeline run gets QA and token-usage accounting.
"""
from __future__ import annotations

# ── Agent name constants ────────────────────────────────────────────────────────

PIPELINE_HEALTH        = "pipeline_health"
SOURCING_QUALITY       = "sourcing_quality"
IMPROVEMENT_ACTION     = "improvement_action"
RESOURCE_OPTIMIZATION  = "resource_optimization"
OFFER_INSIGHTS         = "offer_insights"
EVALUATION             = "evaluation"
OPTIMIZATION           = "optimization"

ALL_INSIGHT_AGENTS: list[str] = [
    PIPELINE_HEALTH,
    SOURCING_QUALITY,
    IMPROVEMENT_ACTION,
    RESOURCE_OPTIMIZATION,
    OFFER_INSIGHTS,
]

SUPPORT_AGENTS: list[str] = [EVALUATION, OPTIMIZATION]

# ── Scenario -> primary agents ──────────────────────────────────────────────────

SCENARIO_AGENTS: dict[str, list[str]] = {
    "pipeline_health": [
        PIPELINE_HEALTH,
        IMPROVEMENT_ACTION,
    ],
    "sourcing_quality": [
        SOURCING_QUALITY,
        PIPELINE_HEALTH,
    ],
    "process_improvement": [
        IMPROVEMENT_ACTION,
        PIPELINE_HEALTH,
        SOURCING_QUALITY,
    ],
    "resource_optimization": [
        RESOURCE_OPTIMIZATION,
        PIPELINE_HEALTH,
    ],
    "offer_analysis": [
        OFFER_INSIGHTS,
        RESOURCE_OPTIMIZATION,
    ],
    "full_analysis": ALL_INSIGHT_AGENTS[:],
}

VALID_SCENARIOS: frozenset[str] = frozenset(SCENARIO_AGENTS)


# ── Public helpers ──────────────────────────────────────────────────────────────

def agents_for_scenario(scenario: str) -> list[str]:
    """Return the ordered list of agents to invoke for *scenario*.

    Evaluation and Optimization are always appended at the end.
    Raises ValueError for unknown scenario names.
    """
    if scenario not in SCENARIO_AGENTS:
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            f"Valid options: {sorted(VALID_SCENARIOS)}"
        )
    primary = list(SCENARIO_AGENTS[scenario])
    return primary + SUPPORT_AGENTS


def validate_and_filter(agent_names: list[str]) -> list[str]:
    """Accept an arbitrary list of agent names and return only recognised ones.

    Unknown names are silently dropped.  The two support agents are appended
    at the end if not already present, preserving the order of insight agents.
    """
    known = set(ALL_INSIGHT_AGENTS) | set(SUPPORT_AGENTS)
    filtered: list[str] = []
    seen: set[str] = set()

    for name in agent_names:
        if name in known and name not in seen:
            filtered.append(name)
            seen.add(name)

    for agent in SUPPORT_AGENTS:
        if agent not in seen:
            filtered.append(agent)

    return filtered


def default_agents() -> list[str]:
    """Return the full agent list used when no scenario can be determined."""
    return agents_for_scenario("full_analysis")
