"""
MCP Tool 2 — fetch_best_practices_by_issue

Queries the ats_interventions ChromaDB collection filtered by issue_type tag
to return structured best-practice entries (steps, timelines, applicable roles).

Design notes:
- InterventionsCollection is lazy-initialised — no ChromaDB connection at import time.
- If ChromaDB is unavailable the function returns a curated built-in fallback so
  the agent can still produce recommendations even without the vector store.
- BestPractice model is defined in vector_store/collections/interventions.py.
"""
from __future__ import annotations

import logging

from vector_store.collections.interventions import BestPractice  # re-export

logger = logging.getLogger(__name__)

_interventions_col = None


def _get_collection():
    global _interventions_col
    if _interventions_col is None:
        from vector_store.collections.interventions import InterventionsCollection
        _interventions_col = InterventionsCollection()
    return _interventions_col


# ── Built-in fallback best practices (used when ChromaDB is empty/unavailable) ──

_FALLBACK_PRACTICES: dict[str, BestPractice] = {
    "slow_assessment": BestPractice(
        practice_id="bp-fallback-001",
        title="Reduce assessment turnaround time",
        steps=[
            "Set SLA targets: phone screen ≤3 days, technical ≤7 days, final ≤14 days",
            "Send automated reminders to interviewers 24 h before stage deadline",
            "Parallelize interview rounds where dependencies allow",
            "Assign a backup interviewer for every active candidate",
        ],
        typical_timeline_weeks=4,
        applicable_roles=["all"],
    ),
    "high_rejection": BestPractice(
        practice_id="bp-fallback-002",
        title="Reduce unstructured rejection rates",
        steps=[
            "Introduce standardised scorecard for each stage",
            "Calibrate interviewers on scoring rubric every quarter",
            "Review and document rejection reasons to identify bias patterns",
            "Add a structured debrief within 24 h of each interview",
        ],
        typical_timeline_weeks=6,
        applicable_roles=["all"],
    ),
    "sourcing_quality": BestPractice(
        practice_id="bp-fallback-003",
        title="Improve candidate sourcing quality",
        steps=[
            "Audit each channel's hire rate quarterly and cut under-performers",
            "Brief headhunters on updated role requirements",
            "Increase employee referral bonus for hard-to-fill roles",
            "Pilot a new channel each quarter and measure 90-day hire rate",
        ],
        typical_timeline_weeks=8,
        applicable_roles=["all"],
    ),
    "offer_decline": BestPractice(
        practice_id="bp-fallback-004",
        title="Improve offer acceptance rate",
        steps=[
            "Benchmark compensation against industry data every 6 months",
            "Add verbal offer call before sending written offer",
            "Survey declined candidates within one week for root-cause data",
            "Introduce flexible working arrangements in offer package",
        ],
        typical_timeline_weeks=3,
        applicable_roles=["all"],
    ),
}


def _normalise_issue_type(issue: str) -> str:
    """Map free-text issue description to a canonical issue_type tag."""
    issue_lower = issue.lower()
    # Assessment/technical checked before generic "fail" so "failing coding test" maps correctly
    if any(w in issue_lower for w in ("slow", "delay", "time", "long", "wait", "stuck",
                                       "assessment", "coding", "technical", "test")):
        return "slow_assessment"
    if any(w in issue_lower for w in ("offer", "accept", "decline", "salary", "comp")):
        return "offer_decline"
    if any(w in issue_lower for w in ("source", "channel", "referral", "linkedin", "quality",
                                       "ghost", "unresponsive")):
        return "sourcing_quality"
    if any(w in issue_lower for w in ("reject", "drop", "fail", "screen", "fit", "culture")):
        return "high_rejection"
    return "slow_assessment"   # safe default


async def fetch_best_practices_by_issue(issue: str) -> list[BestPractice]:
    """Retrieve structured best-practice entries for a described hiring problem.

    First attempts ChromaDB lookup by issue_type tag; falls back to the
    curated built-in table if the collection is empty or unreachable.

    Args:
        issue: Free-text description of the hiring problem.

    Returns:
        List of BestPractice objects with action steps and timelines.
    """
    if not issue or not issue.strip():
        return []

    issue_type = _normalise_issue_type(issue)

    try:
        practices = _get_collection().get_by_issue_type(issue_type)
        if practices:
            return practices
    except Exception as exc:
        logger.warning("fetch_best_practices ChromaDB lookup failed: %s", exc)

    # Fallback — always returns something useful
    fallback = _FALLBACK_PRACTICES.get(issue_type)
    return [fallback] if fallback else list(_FALLBACK_PRACTICES.values())[:1]


__all__ = ["fetch_best_practices_by_issue", "BestPractice"]
