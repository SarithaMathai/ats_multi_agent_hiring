"""
Pure-Python workload calculator for the Resource Optimization Agent.

No LLM, no I/O — takes structured interviewer/stage records and returns
an InterviewerLoad list + WorkloadReport with a text summary for the prompt.

Expected keys in structured_data:
    interviewers : list[dict]  — each dict has interviewer_id, name,
                                 interviews_assigned, avg_hours_per_interview (opt),
                                 avg_rating (opt)
    stages       : list[dict]  — optional; used to cross-check assignment counts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Domain types ─────────────────────────────────────────────────────────────────

@dataclass
class InterviewerLoad:
    interviewer_id: str
    name: str
    interviews_assigned: int
    avg_hours_per_interview: float
    total_hours: float
    avg_rating: float          # 0.0 if not provided
    is_overloaded: bool
    is_underutilised: bool


@dataclass
class WorkloadReport:
    total_interviewers: int
    avg_interviews_per_interviewer: float
    overloaded: list[InterviewerLoad] = field(default_factory=list)
    underutilised: list[InterviewerLoad] = field(default_factory=list)
    loads: list[InterviewerLoad] = field(default_factory=list)
    data_quality: str = "ok"

    def to_text(self) -> str:
        lines: list[str] = [
            f"Total interviewers: {self.total_interviewers}",
            f"Avg interviews assigned: {self.avg_interviews_per_interviewer:.1f}",
        ]
        if self.overloaded:
            lines.append(f"Overloaded ({len(self.overloaded)}):")
            for iv in self.overloaded:
                lines.append(
                    f"  {iv.name} ({iv.interviewer_id}): {iv.interviews_assigned} interviews, "
                    f"{iv.total_hours:.1f} h total"
                    + (f", avg_rating={iv.avg_rating:.2f}" if iv.avg_rating else "")
                )
        if self.underutilised:
            lines.append(f"Underutilised ({len(self.underutilised)}):")
            for iv in self.underutilised:
                lines.append(
                    f"  {iv.name} ({iv.interviewer_id}): {iv.interviews_assigned} interviews"
                )
        if self.loads:
            lines.append("\nFull workload breakdown:")
            for iv in sorted(self.loads, key=lambda x: x.interviews_assigned, reverse=True):
                tag = " [OVERLOADED]" if iv.is_overloaded else (" [UNDER]" if iv.is_underutilised else "")
                lines.append(
                    f"  {iv.name}: {iv.interviews_assigned} interviews, "
                    f"{iv.total_hours:.1f} h{tag}"
                )
        if self.data_quality != "ok":
            lines.append(f"\n[Data quality: {self.data_quality}]")
        return "\n".join(lines)


# ── Thresholds ────────────────────────────────────────────────────────────────────

_OVERLOAD_INTERVIEWS = 15        # > 15 interviews assigned = overloaded
_UNDERUTILISED_INTERVIEWS = 3    # < 3 interviews assigned = underutilised
_DEFAULT_HOURS_PER_INTERVIEW = 1.5


# ── Public API ────────────────────────────────────────────────────────────────────

def compute_workload(structured_data: dict[str, Any]) -> WorkloadReport:
    """Derive WorkloadReport from structured_data supplied by the Coordinator."""
    interviewers_raw: list[dict] = structured_data.get("interviewers", [])

    if not interviewers_raw:
        return WorkloadReport(
            total_interviewers=0,
            avg_interviews_per_interviewer=0.0,
            data_quality="missing",
        )

    loads: list[InterviewerLoad] = []
    for raw in interviewers_raw:
        assigned = int(raw.get("interviews_assigned", 0))
        hrs_each = float(raw.get("avg_hours_per_interview", _DEFAULT_HOURS_PER_INTERVIEW))
        total_h = assigned * hrs_each
        avg_r = float(raw.get("avg_rating", 0.0))

        loads.append(InterviewerLoad(
            interviewer_id=str(raw.get("interviewer_id", "?")),
            name=str(raw.get("name", raw.get("interviewer_id", "Unknown"))),
            interviews_assigned=assigned,
            avg_hours_per_interview=hrs_each,
            total_hours=total_h,
            avg_rating=avg_r,
            is_overloaded=assigned > _OVERLOAD_INTERVIEWS,
            is_underutilised=assigned < _UNDERUTILISED_INTERVIEWS,
        ))

    total = len(loads)
    avg = sum(iv.interviews_assigned for iv in loads) / total if total else 0.0

    return WorkloadReport(
        total_interviewers=total,
        avg_interviews_per_interviewer=avg,
        overloaded=[iv for iv in loads if iv.is_overloaded],
        underutilised=[iv for iv in loads if iv.is_underutilised],
        loads=loads,
        data_quality="ok",
    )
