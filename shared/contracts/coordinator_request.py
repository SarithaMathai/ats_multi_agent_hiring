from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shared.contracts.agent_output import AgentOutput


class CoordinatorRequest(BaseModel):
    query: str
    scenario: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    max_agents: int = 5


class CoordinatorResponse(BaseModel):
    run_id: str
    status: str
    query: str
    agent_outputs: list[AgentOutput] = Field(default_factory=list)
    summary: str = ""
    total_tokens_used: int = 0
    total_latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
