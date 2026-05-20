"""
Assembles individual AgentOutput objects into a single CoordinatorResponse.

Called by CoordinatorAgent after all parallel agent runs complete.
"""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from shared.contracts.agent_output import AgentOutput, Recommendation, TokenUsage


class CoordinatorResponse(BaseModel):
    """Top-level response contract returned by the Coordinator."""

    run_id: str
    query: str
    status: str                          # "success" | "partial" | "error"
    summary: str                         # plain-text narrative for the Streamlit dashboard
    agent_outputs: list[AgentOutput]
    all_recommendations: list[Recommendation]
    total_tokens: int
    total_latency_ms: float
    metadata: dict[str, Any] = {}


def assemble_response(
    run_id: str,
    query: str,
    outputs: list[AgentOutput],
    pipeline_start: float,              # time.monotonic() captured before agents ran
) -> CoordinatorResponse:
    """Build a CoordinatorResponse from the raw per-agent outputs.

    Args:
        run_id:         Unique identifier for this pipeline run.
        query:          The original recruiter query.
        outputs:        AgentOutput from every agent that ran (including routing).
        pipeline_start: monotonic timestamp taken before the pipeline started.

    Returns:
        A fully populated CoordinatorResponse.
    """
    total_latency_ms = (time.monotonic() - pipeline_start) * 1000

    # ── Token aggregation ───────────────────────────────────────────────────────
    total_tokens = sum(
        o.token_usage.total_tokens
        for o in outputs
        if o.status != "skipped"
    )

    # ── Status roll-up ──────────────────────────────────────────────────────────
    statuses = {o.status for o in outputs if o.agent_name != "routing"}
    if "success" in statuses and "error" not in statuses:
        status = "success"
    elif "success" in statuses:
        status = "partial"
    else:
        status = "error"

    # ── Collect all recommendations (deduplicated by title) ────────────────────
    seen_titles: set[str] = set()
    all_recommendations: list[Recommendation] = []
    for output in outputs:
        for rec in output.recommendations:
            if rec.title not in seen_titles:
                all_recommendations.append(rec)
                seen_titles.add(rec.title)

    # Sort: high -> medium -> low priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_recommendations.sort(key=lambda r: priority_order.get(r.priority, 1))

    # ── Narrative summary ───────────────────────────────────────────────────────
    summary = _build_summary(query, outputs, all_recommendations)

    # ── Metadata ────────────────────────────────────────────────────────────────
    agent_statuses = {o.agent_name: o.status for o in outputs}

    return CoordinatorResponse(
        run_id=run_id,
        query=query,
        status=status,
        summary=summary,
        agent_outputs=outputs,
        all_recommendations=all_recommendations,
        total_tokens=total_tokens,
        total_latency_ms=total_latency_ms,
        metadata={
            "agent_statuses": agent_statuses,
            "agents_run": len([o for o in outputs if o.status != "skipped"]),
        },
    )


def _build_summary(
    query: str,
    outputs: list[AgentOutput],
    recommendations: list[Recommendation],
) -> str:
    """Build a plain-text summary paragraph for the dashboard."""
    lines: list[str] = [f"Query: {query}\n"]

    # Top insights from each successful insight agent (skip routing/support)
    skip_agents = {"routing", "evaluation", "optimization"}
    for output in outputs:
        if output.agent_name in skip_agents or output.status != "success":
            continue
        agent_label = output.agent_name.replace("_", " ").title()
        top_insights = output.insights[:3]
        if top_insights:
            lines.append(f"[{agent_label}]")
            for insight in top_insights:
                lines.append(f"  - {insight}")

    # Top 3 high-priority recommendations across all agents
    high_priority = [r for r in recommendations if r.priority == "high"][:3]
    if high_priority:
        lines.append("\nTop Recommendations:")
        for rec in high_priority:
            lines.append(f"  [{rec.priority.upper()}] {rec.title}: {rec.description}")

    return "\n".join(lines)
