"""
Pure-Python cost tracker for the Optimization Agent.

No LLM, no I/O — aggregates token usage and latency across all AgentOutputs
and produces a RunCostSummary with pricing estimates.

Pricing (gpt-4o-mini as of 2025, per 1M tokens):
  Input:  $0.15 / 1M
  Output: $0.60 / 1M
All tiers currently use gpt-4o-mini, so the same rates apply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.contracts.agent_output import AgentOutput

# ── Pricing table (USD per 1M tokens) ───────────────────────────────────────────

_PRICE_PER_M: dict[str, dict[str, float]] = {
    "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
    "gpt-4o":       {"input": 2.50,  "output": 10.00},
    "gpt-4-turbo":  {"input": 10.00, "output": 30.00},
    # Default fallback — matches gpt-4o-mini
    "default":      {"input": 0.15,  "output": 0.60},
}

_COST_FLAG_THRESHOLD_USD = 0.05   # agents spending > $0.05 per run are flagged


# ── Domain types ─────────────────────────────────────────────────────────────────

@dataclass
class AgentCost:
    agent_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    model: str = "gpt-4o-mini"


@dataclass
class RunCostSummary:
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    p95_latency_ms: float
    by_agent: list[AgentCost] = field(default_factory=list)
    flagged_agents: list[str] = field(default_factory=list)   # high cost
    data_quality: str = "ok"

    def to_text(self) -> str:
        lines: list[str] = [
            f"Total tokens  : {self.total_tokens:,}  "
            f"(in={self.total_input_tokens:,}, out={self.total_output_tokens:,})",
            f"Total cost    : ${self.total_cost_usd:.4f} USD",
            f"Avg latency   : {self.avg_latency_ms:.0f} ms",
            f"P95 latency   : {self.p95_latency_ms:.0f} ms",
        ]
        if self.flagged_agents:
            lines.append(f"High-cost agents: {', '.join(self.flagged_agents)}")
        if self.by_agent:
            lines.append("\nPer-agent breakdown:")
            for ac in sorted(self.by_agent, key=lambda x: x.cost_usd, reverse=True):
                flag = " [HIGH COST]" if ac.agent_name in self.flagged_agents else ""
                lines.append(
                    f"  {ac.agent_name}: {ac.total_tokens:,} tokens "
                    f"(${ac.cost_usd:.4f}), {ac.latency_ms:.0f} ms{flag}"
                )
        return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────────

def summarise_run_cost(outputs: list[AgentOutput]) -> RunCostSummary:
    """Aggregate token usage and costs across all agent outputs in this run.

    Args:
        outputs: All AgentOutput objects from the current pipeline run.

    Returns:
        RunCostSummary with per-agent and aggregate cost/latency metrics.
    """
    if not outputs:
        return RunCostSummary(
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            total_cost_usd=0.0,
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            data_quality="missing",
        )

    by_agent: list[AgentCost] = []
    flagged: list[str] = []

    for out in outputs:
        model = out.metadata.get("model", "gpt-4o-mini")
        prices = _PRICE_PER_M.get(model, _PRICE_PER_M["default"])
        in_tok = out.token_usage.input_tokens
        out_tok = out.token_usage.output_tokens
        cost = (in_tok * prices["input"] + out_tok * prices["output"]) / 1_000_000

        agent_cost = AgentCost(
            agent_name=out.agent_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=cost,
            latency_ms=out.latency_ms,
            model=model,
        )
        by_agent.append(agent_cost)
        if cost > _COST_FLAG_THRESHOLD_USD:
            flagged.append(out.agent_name)

    latencies = sorted(ac.latency_ms for ac in by_agent)
    p95_idx = max(0, int(len(latencies) * 0.95) - 1)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = latencies[p95_idx] if latencies else 0.0

    return RunCostSummary(
        total_input_tokens=sum(ac.input_tokens for ac in by_agent),
        total_output_tokens=sum(ac.output_tokens for ac in by_agent),
        total_tokens=sum(ac.total_tokens for ac in by_agent),
        total_cost_usd=sum(ac.cost_usd for ac in by_agent),
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        by_agent=by_agent,
        flagged_agents=flagged,
    )
