"""
Improvement Action Agent — Day 9.

Translates rejection patterns and pipeline inefficiencies into prioritised,
evidence-backed corrective actions using 2 MCP tools:
  Tool 1 — search_similar_interventions : finds matching case studies in ChromaDB
  Tool 2 — fetch_best_practices_by_issue : returns actionable steps + timelines

Workflow inside analyse():
  1. detect_top_issues()          — pure Python, no I/O
  2. mcp.fetch_evidence()         — calls both tools concurrently per top issue
  3. _build_data_summary()        — formats issues + MCP evidence for LLM prompt
  4. _call_llm()                  — RAG + prompt + LLM + output parsing
"""
from __future__ import annotations

import asyncio

from agents.base.base_agent import AgentContext, BaseAgent
from agents.insight.improvement_action.rejection_analyser import RejectionIssue, RejectionReport, detect_top_issues
from mcp_platform.mcp.mcp_client import BestPractice, CaseStudy, MCPClient
from shared.constants.agent_names import IMPROVEMENT_ACTION
from shared.contracts.agent_output import AgentOutput


class ImprovementActionAgent(BaseAgent):
    agent_name = IMPROVEMENT_ACTION
    model_tier = "insight"
    default_collections: list[str] = ["ats_interventions"]

    def __init__(self) -> None:
        super().__init__()
        self.mcp = MCPClient()   # lightweight facade — no heavy I/O yet

    async def analyse(self, context: AgentContext) -> AgentOutput:
        # Step 1 — detect issues from rejection records
        report = detect_top_issues(context.structured_data)

        # Step 2 — call MCP tools for each high/medium issue (max 3 to keep latency low)
        top_issues = [i for i in report.issues if i.severity in ("high", "medium")][:3]
        mcp_results: list[tuple[list[CaseStudy], list[BestPractice]]] = await asyncio.gather(
            *[self.mcp.fetch_evidence(issue.description, role=_extract_role(context))
              for issue in top_issues]
        )

        # Step 3 — build the rich data summary for the prompt
        data_summary = _build_data_summary(report, top_issues, mcp_results, context)

        # Step 4 — call LLM (RAG against ats_interventions + prompt + parse)
        output = await self._call_llm(context, data_summary=data_summary)

        # Attach computed metadata for downstream agents / dashboard
        output.metadata["rejection_report"] = {
            "total_rejections": report.total_rejections,
            "overall_rejection_rate": round(report.overall_rejection_rate, 4),
            "top_issues": [
                {"issue_type": i.issue_type, "severity": i.severity, "count": i.affected_count}
                for i in report.issues[:5]
            ],
        }
        output.metadata["mcp_case_study_count"] = sum(len(cs) for cs, _ in mcp_results)
        return output


# ── Private helpers ──────────────────────────────────────────────────────────────

def _extract_role(context: AgentContext) -> str | None:
    """Pull a job role from filters if the caller supplied one."""
    return context.filters.get("role") or context.filters.get("position") or None


def _build_data_summary(
    report: RejectionReport,
    top_issues: list[RejectionIssue],
    mcp_results: list[tuple[list[CaseStudy], list[BestPractice]]],
    context: AgentContext,
) -> str:
    lines: list[str] = [report.to_text()]

    # Append MCP evidence per issue
    for issue, (case_studies, practices) in zip(top_issues, mcp_results):
        lines.append(f"\n--- Evidence for: {issue.issue_type} ---")

        if case_studies:
            lines.append("Case studies from similar organisations:")
            for cs in case_studies[:3]:
                lines.append(
                    f"  [{cs.case_study_id}] {cs.title} | issue: {cs.issue_type} | "
                    f"impact: {cs.observed_impact_pct:.0f}% improvement | "
                    f"timeline: {cs.implementation_weeks} weeks"
                )
                if cs.excerpt:
                    lines.append(f"    excerpt: {cs.excerpt[:200]}")
        else:
            lines.append("  No matching case studies found in knowledge base.")

        if practices:
            lines.append("Best-practice action steps:")
            for bp in practices[:2]:
                lines.append(f"  [{bp.practice_id}] {bp.title} (~{bp.typical_timeline_weeks} weeks)")
                for step in bp.steps[:4]:
                    lines.append(f"    • {step}")
        else:
            lines.append("  No best practices retrieved.")

    # Surface context from previous agents (e.g. PipelineHealthAgent)
    for prev in context.previous_outputs:
        if prev.agent_name in ("pipeline_health", "sourcing_quality") and prev.insights:
            lines.append(f"\nContext from {prev.agent_name} agent:")
            for ins in prev.insights[:2]:
                lines.append(f"  - {ins}")

    return "\n".join(lines)
