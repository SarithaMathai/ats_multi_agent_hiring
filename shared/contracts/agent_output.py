from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Evidence(BaseModel):
    source: str
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    collection: str | None = None
    document_id: str | None = None


class Recommendation(BaseModel):
    title: str
    description: str
    priority: Literal["high", "medium", "low"] = "medium"
    effort: Literal["low", "medium", "high"] = "medium"
    evidence_ids: list[str] = Field(default_factory=list)


class AgentOutput(BaseModel):
    agent_name: str
    status: Literal["success", "error", "skipped"]
    insights: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    token_usage: TokenUsage
    latency_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def skipped(cls, agent_name: str) -> AgentOutput:
        return cls(
            agent_name=agent_name,
            status="skipped",
            confidence_score=0.0,
            token_usage=TokenUsage(input_tokens=0, output_tokens=0),
            latency_ms=0.0,
        )

    @classmethod
    def error(cls, agent_name: str, reason: str, latency_ms: float = 0.0) -> AgentOutput:
        return cls(
            agent_name=agent_name,
            status="error",
            confidence_score=0.0,
            token_usage=TokenUsage(input_tokens=0, output_tokens=0),
            latency_ms=latency_ms,
            metadata={"error": reason},
        )
