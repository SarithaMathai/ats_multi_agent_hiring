"""
Metrics endpoints — pre-aggregated hiring data for the Reports dashboard.

GET /api/v1/metrics/live
    Fetches live PostgreSQL data via HiringAnalysisWorkflow._fetch_structured_data(),
    aggregates it into chart-ready JSON, and returns it.  No LLM involved — fast.

GET /api/v1/metrics/runs
    Returns paginated run records from the persistent JSONL store.
    Optional ?scenario= filter.

GET /api/v1/metrics/runs/{run_id}
    Returns a single run record by run_id.

GET /api/v1/metrics/scenarios/summary
    Returns each scenario name and how many times it has been run.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from orchestration.state import run_history_store

router = APIRouter(tags=["metrics"])


# ── Dependency ────────────────────────────────────────────────────────────────

def _get_workflow():
    from app.main import get_workflow
    return get_workflow()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/live")
async def get_live_metrics(workflow=Depends(_get_workflow)) -> dict[str, Any]:
    """Return chart-ready hiring metrics aggregated from live PostgreSQL data."""
    try:
        raw = await workflow._fetch_structured_data({})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _build_metrics_payload(raw)


@router.get("/runs")
def get_run_history(
    limit: int = Query(default=50, ge=1, le=200),
    scenario: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Return recent run records (newest first), optionally filtered by scenario."""
    return run_history_store.list_runs(limit=limit, scenario=scenario or None)


@router.get("/runs/{run_id}")
def get_run_by_id(run_id: str) -> dict[str, Any]:
    """Return a single run record by run_id."""
    record = run_history_store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return record


@router.get("/scenarios/summary")
def get_scenarios_summary() -> list[dict[str, Any]]:
    """Return each scenario and its historical run count."""
    return run_history_store.list_scenarios_with_counts()


# ── Aggregation logic ─────────────────────────────────────────────────────────

_STAGE_ORDER = [
    "application_review",
    "phone_screen",
    "technical_assessment",
    "panel_interview",
    "final_interview",
    "offer",
]

_STAGE_LABEL = {
    "application_review":   "Application Review",
    "phone_screen":         "Phone Screen",
    "technical_assessment": "Technical Assessment",
    "panel_interview":      "Panel Interview",
    "final_interview":      "Final Interview",
    "offer":                "Offer",
}


def _build_metrics_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Transform raw PostgreSQL rows into chart-ready aggregates.

    Input shapes (from HiringAnalysisWorkflow._fetch_structured_data):
      stages:       {stage_name, candidates_entered, candidates_exited, avg_days_in_stage}
      candidates:   {source_channel, status, quality_score, days_in_current_stage}
      interviewers: {name, interviews_assigned, avg_rating}   avg_rating is 0-1 pass-rate
      offers:       {position, status, decline_reason, salary_offered, days_to_respond}

    Output shapes consumed by the Reports chart functions.
    """
    stages       = data.get("stages", [])
    candidates   = data.get("candidates", [])
    interviewers = data.get("interviewers", [])
    offers       = data.get("offers", [])

    # ── Pipeline funnel ───────────────────────────────────────────────────────
    stage_map = {s["stage_name"]: s for s in stages}
    funnel: list[dict] = []
    for key in _STAGE_ORDER:
        s = stage_map.get(key)
        if not s:
            continue
        entered = int(s.get("candidates_entered", 0))
        exited  = int(s.get("candidates_exited",  0))
        funnel.append({
            "stage":           _STAGE_LABEL.get(key, key),
            "entered":         entered,
            "exited":          exited,
            "conversion_pct":  round(exited / entered * 100, 1) if entered else 0.0,
            "avg_days":        round(float(s.get("avg_days_in_stage", 0)), 1),
        })

    # ── Sourcing channels ─────────────────────────────────────────────────────
    ch_total:   dict[str, int]         = defaultdict(int)
    ch_hired:   dict[str, int]         = defaultdict(int)
    ch_quality: dict[str, list[float]] = defaultdict(list)
    for c in candidates:
        ch = c.get("source_channel", "Unknown")
        ch_total[ch] += 1
        if c.get("status") == "hired":
            ch_hired[ch] += 1
        q = c.get("quality_score")
        if q is not None:
            ch_quality[ch].append(float(q))

    channels: list[dict] = []
    for ch, total in sorted(ch_total.items(), key=lambda x: -x[1]):
        hired = ch_hired[ch]
        channels.append({
            "channel":      ch,
            "total":        total,
            "hired":        hired,
            "hire_rate_pct": round(hired / total * 100, 1) if total else 0.0,
            "avg_quality":  round(sum(ch_quality[ch]) / len(ch_quality[ch]), 2)
                            if ch_quality[ch] else 0.0,
        })

    # ── Interviewers ──────────────────────────────────────────────────────────
    # avg_rating from DB is a pass-rate fraction (0-1); multiply by 100 for display
    interviewer_rows: list[dict] = [
        {
            "name":                i.get("name", "?"),
            "interviews_assigned": int(i.get("interviews_assigned", 0)),
            "pass_rate_pct":       round(float(i.get("avg_rating", 0)) * 100, 1),
        }
        for i in interviewers
    ]

    # ── Offers ────────────────────────────────────────────────────────────────
    offer_totals:  dict[str, int] = defaultdict(int)
    pos_total:     dict[str, int] = defaultdict(int)
    pos_accepted:  dict[str, int] = defaultdict(int)
    decline_rsns:  dict[str, int] = defaultdict(int)
    salary_by_pos: dict[str, list[float]] = defaultdict(list)

    for o in offers:
        status = o.get("status", "pending")
        offer_totals[status] += 1
        pos = o.get("position", "Unknown")
        pos_total[pos] += 1
        if status == "accepted":
            pos_accepted[pos] += 1
        if reason := o.get("decline_reason"):
            decline_rsns[reason] += 1
        salary = o.get("salary_offered")
        if salary is not None:
            try:
                salary_by_pos[pos].append(float(salary))
            except (TypeError, ValueError):
                pass

    by_position: list[dict] = [
        {
            "position":   pos,
            "total":      pos_total[pos],
            "accepted":   pos_accepted[pos],
            "rate_pct":   round(pos_accepted[pos] / pos_total[pos] * 100, 1)
                          if pos_total[pos] else 0.0,
            "avg_salary": round(sum(salary_by_pos[pos]) / len(salary_by_pos[pos]))
                          if salary_by_pos[pos] else None,
        }
        for pos in sorted(pos_total)
    ]

    # ── Summary KPIs ──────────────────────────────────────────────────────────
    total_cands = len(candidates)
    total_hired = sum(1 for c in candidates if c.get("status") == "hired")
    stuck       = sum(1 for c in candidates if float(c.get("days_in_current_stage", 0)) > 14)
    overloaded  = sum(1 for i in interviewers if int(i.get("interviews_assigned", 0)) > 15)
    avg_time_to_hire = round(sum(f["avg_days"] for f in funnel), 1)

    summary_stats: dict[str, Any] = {
        "total_candidates":      total_cands,
        "total_hired":           total_hired,
        "overall_hire_rate_pct": round(total_hired / total_cands * 100, 1) if total_cands else 0.0,
        "stuck_candidates":      stuck,
        "overloaded_interviewers": overloaded,
        "total_interviewers":    len(interviewers),
        "avg_time_to_hire_days": avg_time_to_hire,
        "total_offers":          len(offers),
        "accepted_offers":       offer_totals.get("accepted", 0),
        "declined_offers":       offer_totals.get("declined", 0),
        "pending_offers":        offer_totals.get("pending", 0),
    }

    return {
        "funnel":       funnel,
        "channels":     channels,
        "interviewers": interviewer_rows,
        "offers": {
            "total":           len(offers),
            "accepted":        offer_totals.get("accepted", 0),
            "declined":        offer_totals.get("declined", 0),
            "pending":         offer_totals.get("pending", 0),
            "by_position":     by_position,
            "decline_reasons": dict(decline_rsns),
        },
        "summary_stats": summary_stats,
    }
