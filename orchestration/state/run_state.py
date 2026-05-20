"""
RunState — lightweight in-memory record of a single workflow execution.

Created by HiringAnalysisWorkflow before calling the Coordinator and
populated from the CoordinatorResponse after the pipeline completes.
Not persisted to DB here — persistence is handled at the API layer (Day 12).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class RunState(BaseModel):
    """Snapshot of everything that happened in one workflow run."""

    run_id: str
    scenario_name: str | None = None       # None for free-form queries
    query: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: str = "running"                # "running" | "success" | "partial" | "error"
    agents_run: list[str] = Field(default_factory=list)
    forced_agents: list[str] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Cost constant — gpt-4o-mini blended rate (input+output average)
    _BLENDED_COST_PER_TOKEN: float = 0.000_000_375

    def mark_complete(
        self,
        status: str,
        agents_run: list[str],
        total_tokens: int,
        total_latency_ms: float,
    ) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.status = status
        self.agents_run = agents_run
        self.total_tokens = total_tokens
        self.total_latency_ms = total_latency_ms
        self.total_cost_usd = total_tokens * self._BLENDED_COST_PER_TOKEN

    def duration_ms(self) -> float:
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return self.total_latency_ms

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario": self.scenario_name,
            "status": self.status,
            "agents_run": self.agents_run,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_latency_ms": round(self.total_latency_ms, 1),
        }
