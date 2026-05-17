"""
Pure-Python claim verifier for the Evaluation Agent.

No LLM, no I/O — inspects each AgentOutput for evidence sufficiency,
confidence plausibility, and internal consistency.

Rules applied:
  - status must be "success" (not "error" or "skipped")
  - at least 1 insight must be present
  - confidence_score >= 0.5 (below = limited data — flag but don't fail)
  - at least 1 evidence item OR confidence_score >= 0.7 (agent must cite something)
  - no insight may be duplicated across agents (cross-agent dedup check)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.contracts.agent_output import AgentOutput


# ── Domain types ─────────────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    agent_name: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    original_confidence: float = 0.0
    adjusted_confidence: float = 0.0   # downgraded when issues are found


@dataclass
class VerificationSummary:
    total_agents: int
    passed: int
    flagged: int
    results: list[VerificationResult] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"Verified {self.total_agents} agent outputs: "
            f"{self.passed} passed, {self.flagged} flagged."
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FLAG"
            conf_note = (
                f"  confidence: {r.original_confidence:.2f}"
                + (f" -> {r.adjusted_confidence:.2f} (downgraded)" if r.adjusted_confidence < r.original_confidence else "")
            )
            lines.append(f"\n  [{status}] {r.agent_name}")
            lines.append(conf_note)
            for issue in r.issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines)


# ── Thresholds ────────────────────────────────────────────────────────────────────

_MIN_CONFIDENCE = 0.5
_MIN_INSIGHTS = 1
_CONFIDENCE_PENALTY = 0.15   # subtracted per failing check, floor 0.1


# ── Public API ────────────────────────────────────────────────────────────────────

def verify_outputs(outputs: list[AgentOutput]) -> VerificationSummary:
    """Inspect every AgentOutput and flag quality issues.

    Args:
        outputs: All insight (and support) agent outputs from the current run.

    Returns:
        VerificationSummary with per-agent VerificationResult objects.
    """
    if not outputs:
        return VerificationSummary(total_agents=0, passed=0, flagged=0)

    # Build cross-agent insight set for duplicate detection
    all_insight_texts: list[str] = []
    for o in outputs:
        all_insight_texts.extend(o.insights)
    insight_counts: dict[str, int] = {}
    for text in all_insight_texts:
        key = text.strip().lower()[:80]
        insight_counts[key] = insight_counts.get(key, 0) + 1

    results: list[VerificationResult] = []

    for output in outputs:
        issues: list[str] = []
        confidence = output.confidence_score

        # Rule 1 — must have succeeded
        if output.status != "success":
            issues.append(f"status={output.status!r} — agent did not complete successfully")

        # Rule 2 — must have at least one insight
        if len(output.insights) < _MIN_INSIGHTS:
            issues.append("no insights returned — data may be insufficient")

        # Rule 3 — confidence floor
        if output.confidence_score < _MIN_CONFIDENCE:
            issues.append(
                f"low confidence ({output.confidence_score:.2f}) — "
                "claims may not be well-supported"
            )

        # Rule 4 — evidence or high-confidence assertion
        if not output.evidence and output.confidence_score < 0.70:
            issues.append(
                "no RAG evidence cited and confidence < 0.70 — "
                "recommendations lack external grounding"
            )

        # Rule 5 — duplicate insights across agents
        dup_insights = [
            t for t in output.insights
            if insight_counts.get(t.strip().lower()[:80], 0) > 1
        ]
        if dup_insights:
            issues.append(
                f"{len(dup_insights)} insight(s) duplicated across agents — "
                "may indicate overlap in agent scope"
            )

        # Compute adjusted confidence
        penalties = len(issues) * _CONFIDENCE_PENALTY
        adjusted = max(0.1, confidence - penalties)

        results.append(VerificationResult(
            agent_name=output.agent_name,
            passed=len(issues) == 0,
            issues=issues,
            original_confidence=confidence,
            adjusted_confidence=adjusted,
        ))

    passed = sum(1 for r in results if r.passed)
    return VerificationSummary(
        total_agents=len(results),
        passed=passed,
        flagged=len(results) - passed,
        results=results,
    )
