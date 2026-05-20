"""
Canonical import point for AgentContext in the orchestration layer.

AgentContext is defined in agents.base.base_agent and re-exported here
so orchestration code, scenarios, and workflows have a stable import path
that does not depend on the agents package internals.
"""
from agents.base.base_agent import AgentContext  # noqa: F401 — re-export

__all__ = ["AgentContext"]
