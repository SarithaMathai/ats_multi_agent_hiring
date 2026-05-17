"""
Pure-Python rejection pattern analyser for the Improvement Action Agent.

No LLM, no I/O — takes structured rejection records and surfaces the top
hiring issues to investigate.

Expected keys in structured_data:
    rejections  : list[dict]  — each dict has:
                    candidate_id, stage, reason (or rejection_category),
                    role (optional), rejection_category (optional)
    candidates  : list[dict]  — optional; used to count total pipeline size
                    for computing rejection rates
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


# ── Domain types ─────────────────────────────────────────────────────────────────

@dataclass
class RejectionIssue:
    issue_type: str              # canonical tag used by MCP tools
    description: str             # human-readable text injected into LLM prompt
    affected_count: int          # number of rejections matching this issue
    affected_stages: list[str]   # pipeline stages where rejections cluster
    severity: str                # "high" | "medium" | "low"
    top_reasons: list[str] = field(default_factory=list)   # top rejection reasons


@dataclass
class RejectionReport:
    total_rejections: int
    total_candidates: int
    overall_rejection_rate: float
    issues: list[RejectionIssue] = field(default_factory=list)
    data_quality: str = "ok"     # "ok" | "partial" | "missing"

    def to_text(self) -> str:
        lines: list[str] = [
            f"Total rejections: {self.total_rejections} / {self.total_candidates} candidates "
            f"({self.overall_rejection_rate:.1%} rejection rate)",
        ]
        for iss in self.issues:
            lines.append(
                f"\n[{iss.severity.upper()}] {iss.issue_type}: {iss.affected_count} rejections "
                f"at stage(s) {', '.join(iss.affected_stages)}"
            )
            lines.append(f"  Description: {iss.description}")
            if iss.top_reasons:
                lines.append(f"  Top reasons: {'; '.join(iss.top_reasons[:3])}")
        if self.data_quality != "ok":
            lines.append(f"\n[Data quality: {self.data_quality}]")
        return "\n".join(lines)


# ── Issue classification ──────────────────────────────────────────────────────────

# Maps rejection_category / reason keywords to canonical issue types
_CATEGORY_ISSUE_MAP: list[tuple[list[str], str]] = [
    (["technical", "coding", "assessment", "test", "skill"],     "slow_assessment"),
    (["cultural", "culture", "fit", "attitude", "behaviour"],    "high_rejection"),
    (["experience", "seniority", "level", "junior", "senior"],   "high_rejection"),
    (["communication", "english", "language", "articulate"],     "high_rejection"),
    (["salary", "compensation", "offer", "package", "declined"], "offer_decline"),
    (["ghosting", "no-show", "unresponsive", "disappeared"],     "sourcing_quality"),
    (["overqualified", "over-qualified"],                        "high_rejection"),
]

_SEVERITY_THRESHOLDS = {"high": 0.25, "medium": 0.10}   # fraction of total rejections


def _classify_reason(reason: str) -> str:
    reason_lower = reason.lower()
    for keywords, issue_type in _CATEGORY_ISSUE_MAP:
        if any(kw in reason_lower for kw in keywords):
            return issue_type
    return "high_rejection"   # default bucket


# ── Public API ────────────────────────────────────────────────────────────────────

def detect_top_issues(structured_data: dict) -> RejectionReport:
    """Analyse rejection records and surface the most impactful hiring issues.

    Args:
        structured_data: The dict from AgentContext.structured_data.
                         Uses keys: "rejections", "candidates" (optional).

    Returns:
        RejectionReport with a prioritised list of RejectionIssue items.
    """
    rejections: list[dict] = structured_data.get("rejections", [])
    candidates: list[dict] = structured_data.get("candidates", [])

    if not rejections:
        return RejectionReport(
            total_rejections=0,
            total_candidates=len(candidates),
            overall_rejection_rate=0.0,
            data_quality="missing",
        )

    total_rej = len(rejections)
    total_cands = len(candidates) if candidates else total_rej

    # Bucket by issue_type → track stages and reason strings
    issue_stages: dict[str, list[str]] = defaultdict(list)
    issue_reasons: dict[str, list[str]] = defaultdict(list)
    issue_counts: Counter = Counter()

    for rec in rejections:
        raw_reason = (
            rec.get("rejection_category")
            or rec.get("reason")
            or "unknown"
        )
        issue_type = _classify_reason(raw_reason)
        stage = rec.get("stage", "unknown")
        issue_counts[issue_type] += 1
        issue_stages[issue_type].append(stage)
        issue_reasons[issue_type].append(raw_reason)

    # Build RejectionIssue per bucket, ordered by count descending
    issues: list[RejectionIssue] = []
    for issue_type, count in issue_counts.most_common(5):
        fraction = count / total_rej
        if fraction >= _SEVERITY_THRESHOLDS["high"]:
            severity = "high"
        elif fraction >= _SEVERITY_THRESHOLDS["medium"]:
            severity = "medium"
        else:
            severity = "low"

        # Deduplicate stages and reasons
        stages = sorted(set(issue_stages[issue_type]))
        top_reasons = [r for r, _ in Counter(issue_reasons[issue_type]).most_common(3)]

        description = _describe_issue(issue_type, count, stages, total_rej)

        issues.append(RejectionIssue(
            issue_type=issue_type,
            description=description,
            affected_count=count,
            affected_stages=stages,
            severity=severity,
            top_reasons=top_reasons,
        ))

    return RejectionReport(
        total_rejections=total_rej,
        total_candidates=total_cands,
        overall_rejection_rate=total_rej / total_cands if total_cands > 0 else 0.0,
        issues=issues,
        data_quality="ok",
    )


def _describe_issue(issue_type: str, count: int, stages: list[str], total: int) -> str:
    pct = count / total if total else 0
    stage_str = ", ".join(stages[:3]) or "unspecified stage"
    templates = {
        "slow_assessment": (
            f"{count} candidates ({pct:.0%}) rejected at technical/assessment stage(s) "
            f"({stage_str}) — possible slow or inconsistent evaluation process"
        ),
        "high_rejection": (
            f"{count} candidates ({pct:.0%}) rejected for quality/fit reasons at "
            f"{stage_str} — may indicate sourcing mismatch or bias in screening"
        ),
        "offer_decline": (
            f"{count} candidates ({pct:.0%}) declined at offer stage — likely compensation "
            f"or package misalignment"
        ),
        "sourcing_quality": (
            f"{count} candidates ({pct:.0%}) lost to ghosting or non-engagement at "
            f"{stage_str} — sourcing channel quality concern"
        ),
    }
    return templates.get(issue_type, f"{count} rejections ({pct:.0%}) at {stage_str}")
