"""
Pure-Python metrics for pipeline health analysis.

No LLM, no I/O — takes structured data dicts and returns a PipelineMetrics
dataclass plus a human-readable text summary for injection into the LLM prompt.

Expected keys in structured_data:
    stages      : list[dict]  — each dict has stage_name, candidates_entered,
                                candidates_exited, avg_days_in_stage
    candidates  : list[dict]  — each dict has candidate_id, current_stage,
                                days_in_current_stage, status
                  (optional but improves stuck-candidate detection)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Domain types ────────────────────────────────────────────────────────────────

@dataclass
class StageMetrics:
    stage_name: str
    candidates_entered: int
    candidates_exited: int
    avg_days_in_stage: float
    conversion_rate: float       # candidates_exited / candidates_entered
    drop_off_rate: float         # 1 - conversion_rate
    is_bottleneck: bool          # avg_days > threshold or conversion_rate very low


@dataclass
class PipelineMetrics:
    total_candidates: int
    overall_conversion_rate: float       # first stage entered → last stage exited
    avg_total_pipeline_days: float
    stages: list[StageMetrics] = field(default_factory=list)
    stuck_candidates: list[dict[str, Any]] = field(default_factory=list)
    bottleneck_stages: list[str] = field(default_factory=list)
    worst_drop_off_stage: str = ""
    data_quality: str = "ok"             # "ok" | "partial" | "missing"

    def to_text(self) -> str:
        """Return a concise multi-line text block for the LLM prompt."""
        lines: list[str] = [
            f"Total candidates in pipeline: {self.total_candidates}",
            f"Overall conversion rate: {self.overall_conversion_rate:.1%}",
            f"Average days end-to-end: {self.avg_total_pipeline_days:.1f}",
        ]

        if self.stages:
            lines.append("\nStage-by-stage breakdown:")
            for s in self.stages:
                bottleneck_tag = " [BOTTLENECK]" if s.is_bottleneck else ""
                lines.append(
                    f"  {s.stage_name}: entered={s.candidates_entered}, "
                    f"exited={s.candidates_exited}, "
                    f"conversion={s.conversion_rate:.1%}, "
                    f"avg_days={s.avg_days_in_stage:.1f}{bottleneck_tag}"
                )

        if self.bottleneck_stages:
            lines.append(f"\nBottleneck stages: {', '.join(self.bottleneck_stages)}")

        if self.worst_drop_off_stage:
            lines.append(f"Worst drop-off stage: {self.worst_drop_off_stage}")

        if self.stuck_candidates:
            lines.append(f"\nStuck candidates (overdue): {len(self.stuck_candidates)}")
            for c in self.stuck_candidates[:5]:           # show at most 5 examples
                lines.append(
                    f"  id={c.get('candidate_id', '?')}, "
                    f"stage={c.get('current_stage', '?')}, "
                    f"days={c.get('days_in_current_stage', '?')}"
                )
            if len(self.stuck_candidates) > 5:
                lines.append(f"  … and {len(self.stuck_candidates) - 5} more")

        if self.data_quality != "ok":
            lines.append(f"\n[Data quality: {self.data_quality}]")

        return "\n".join(lines)


# ── Stage thresholds ─────────────────────────────────────────────────────────────

# Stages whose avg time exceeding these thresholds are flagged as bottlenecks.
_STAGE_DAY_THRESHOLDS: dict[str, float] = {
    "screening":    3.0,
    "phone_screen": 5.0,
    "interview":    14.0,
    "technical":    10.0,
    "offer":        7.0,
    "background":   10.0,
}
_DEFAULT_DAY_THRESHOLD = 10.0
_LOW_CONVERSION_THRESHOLD = 0.40   # below 40 % considered a bottleneck
_STUCK_DAYS_THRESHOLD = 14.0       # candidate in stage > 14 days = stuck


# ── Public API ───────────────────────────────────────────────────────────────────

def compute_pipeline_metrics(structured_data: dict[str, Any]) -> PipelineMetrics:
    """Derive PipelineMetrics from the structured_data dict supplied by the Coordinator."""
    stages_raw: list[dict] = structured_data.get("stages", [])
    candidates_raw: list[dict] = structured_data.get("candidates", [])

    if not stages_raw:
        return PipelineMetrics(
            total_candidates=0,
            overall_conversion_rate=0.0,
            avg_total_pipeline_days=0.0,
            data_quality="missing",
        )

    stage_metrics: list[StageMetrics] = []
    bottleneck_names: list[str] = []
    worst_drop_off_stage = ""
    worst_drop_off = 1.0   # higher is less dropped

    for raw in stages_raw:
        name = raw.get("stage_name", "unknown")
        entered = int(raw.get("candidates_entered", 0))
        exited = int(raw.get("candidates_exited", 0))
        avg_days = float(raw.get("avg_days_in_stage", 0.0))

        conversion = (exited / entered) if entered > 0 else 0.0
        drop_off = 1.0 - conversion

        day_threshold = _STAGE_DAY_THRESHOLDS.get(name.lower(), _DEFAULT_DAY_THRESHOLD)
        is_bottleneck = avg_days > day_threshold or conversion < _LOW_CONVERSION_THRESHOLD

        sm = StageMetrics(
            stage_name=name,
            candidates_entered=entered,
            candidates_exited=exited,
            avg_days_in_stage=avg_days,
            conversion_rate=conversion,
            drop_off_rate=drop_off,
            is_bottleneck=is_bottleneck,
        )
        stage_metrics.append(sm)

        if is_bottleneck:
            bottleneck_names.append(name)

        if entered > 0 and drop_off > (1.0 - worst_drop_off):
            worst_drop_off = conversion
            worst_drop_off_stage = name

    # Overall stats
    first_stage = stage_metrics[0] if stage_metrics else None
    last_stage = stage_metrics[-1] if stage_metrics else None
    total_candidates = first_stage.candidates_entered if first_stage else 0
    final_converted = last_stage.candidates_exited if last_stage else 0
    overall_conversion = (final_converted / total_candidates) if total_candidates > 0 else 0.0
    avg_total_days = sum(s.avg_days_in_stage for s in stage_metrics)

    # Stuck candidates
    stuck: list[dict] = [
        c for c in candidates_raw
        if float(c.get("days_in_current_stage", 0)) > _STUCK_DAYS_THRESHOLD
        and c.get("status", "").lower() not in ("hired", "rejected", "withdrawn")
    ]

    data_quality = "ok" if stages_raw else ("partial" if candidates_raw else "missing")

    return PipelineMetrics(
        total_candidates=total_candidates,
        overall_conversion_rate=overall_conversion,
        avg_total_pipeline_days=avg_total_days,
        stages=stage_metrics,
        stuck_candidates=stuck,
        bottleneck_stages=bottleneck_names,
        worst_drop_off_stage=worst_drop_off_stage,
        data_quality=data_quality,
    )
