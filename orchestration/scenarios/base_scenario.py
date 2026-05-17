"""
BaseScenario — configuration record for a named hiring analysis scenario.

Each scenario declares:
  name            : unique slug used in API calls and the UI
  description     : human-readable label for the Streamlit dropdown
  default_query   : the pre-built recruiter question sent to the LLM
  forced_agents   : ordered list of agents to run (bypasses RoutingAgent LLM call)
  required_data_keys : structured_data keys the caller must supply for full results

Scenario subclasses live in orchestration/scenarios/<name>.py.
HiringAnalysisWorkflow auto-discovers them via _REGISTRY.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaseScenario:
    name: str
    description: str
    default_query: str
    forced_agents: list[str]
    required_data_keys: list[str] = field(default_factory=list)

    def build_query(self, override: str | None = None) -> str:
        """Return the override query if supplied, else the scenario default."""
        return override.strip() if override and override.strip() else self.default_query

    def missing_data_keys(self, structured_data: dict[str, Any]) -> list[str]:
        """Return which required_data_keys are absent from structured_data."""
        return [k for k in self.required_data_keys if k not in structured_data]
