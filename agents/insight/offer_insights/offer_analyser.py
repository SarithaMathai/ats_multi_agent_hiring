"""
Pure-Python offer analyser for the Offer Insights Agent.

No LLM, no I/O — takes structured offer records and returns per-position
stats and an OfferReport with a text summary for the LLM prompt.

Expected keys in structured_data:
    offers : list[dict]  — each dict has:
               candidate_id, position, salary_offered (optional float),
               status ("accepted" | "declined" | "pending" | "withdrawn"),
               days_to_respond (optional int),
               decline_reason (optional str)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


# ── Domain types ─────────────────────────────────────────────────────────────────

@dataclass
class PositionOfferStats:
    position: str
    total_offers: int
    accepted: int
    declined: int
    pending: int
    acceptance_rate: float
    avg_salary_offered: float        # 0.0 if not provided
    avg_days_to_respond: float       # 0.0 if not provided
    top_decline_reasons: list[str] = field(default_factory=list)


@dataclass
class OfferReport:
    total_offers: int
    accepted: int
    declined: int
    pending: int
    overall_acceptance_rate: float
    avg_days_to_respond: float
    avg_salary_offered: float
    by_position: list[PositionOfferStats] = field(default_factory=list)
    declining_positions: list[str] = field(default_factory=list)   # acceptance < threshold
    salary_flags: list[str] = field(default_factory=list)           # salary < market proxy
    data_quality: str = "ok"

    def to_text(self) -> str:
        lines: list[str] = [
            f"Total offers: {self.total_offers}  |  "
            f"Accepted: {self.accepted}  |  Declined: {self.declined}  |  Pending: {self.pending}",
            f"Overall acceptance rate: {self.overall_acceptance_rate:.1%}",
            f"Avg days to respond: {self.avg_days_to_respond:.1f}",
        ]
        if self.avg_salary_offered:
            lines.append(f"Avg salary offered: ${self.avg_salary_offered:,.0f}")
        if self.declining_positions:
            lines.append(f"Positions with low acceptance (<50%): {', '.join(self.declining_positions)}")
        if self.salary_flags:
            lines.append(f"Salary concerns: {'; '.join(self.salary_flags)}")
        if self.by_position:
            lines.append("\nPer-position breakdown:")
            for p in sorted(self.by_position, key=lambda x: x.total_offers, reverse=True):
                sal = f", avg_salary=${p.avg_salary_offered:,.0f}" if p.avg_salary_offered else ""
                lines.append(
                    f"  {p.position}: offers={p.total_offers}, "
                    f"accepted={p.accepted}, rate={p.acceptance_rate:.1%}{sal}"
                )
                if p.top_decline_reasons:
                    lines.append(f"    decline reasons: {'; '.join(p.top_decline_reasons[:2])}")
        if self.data_quality != "ok":
            lines.append(f"\n[Data quality: {self.data_quality}]")
        return "\n".join(lines)


# ── Thresholds ────────────────────────────────────────────────────────────────────

_LOW_ACCEPTANCE_THRESHOLD = 0.50    # positions below 50% acceptance are flagged
_SALARY_DECLINE_KEYWORDS = {"salary", "compensation", "pay", "money", "package", "low offer"}


# ── Public API ────────────────────────────────────────────────────────────────────

def compute_offer_stats(structured_data: dict[str, Any]) -> OfferReport:
    """Derive OfferReport from structured_data supplied by the Coordinator."""
    offers_raw: list[dict] = structured_data.get("offers", [])

    if not offers_raw:
        return OfferReport(
            total_offers=0,
            accepted=0,
            declined=0,
            pending=0,
            overall_acceptance_rate=0.0,
            avg_days_to_respond=0.0,
            avg_salary_offered=0.0,
            data_quality="missing",
        )

    # Aggregate overall totals
    total = len(offers_raw)
    accepted = sum(1 for o in offers_raw if o.get("status", "").lower() == "accepted")
    declined = sum(1 for o in offers_raw if o.get("status", "").lower() == "declined")
    pending = total - accepted - declined

    day_list = [float(o["days_to_respond"]) for o in offers_raw if o.get("days_to_respond") is not None]
    sal_list = [float(o["salary_offered"]) for o in offers_raw if o.get("salary_offered") is not None]
    avg_days = sum(day_list) / len(day_list) if day_list else 0.0
    avg_sal = sum(sal_list) / len(sal_list) if sal_list else 0.0

    # Per-position aggregation
    pos_buckets: dict[str, list[dict]] = defaultdict(list)
    for o in offers_raw:
        pos_buckets[o.get("position", "Unspecified")].append(o)

    by_position: list[PositionOfferStats] = []
    declining_positions: list[str] = []
    salary_flags: list[str] = []

    for pos, pos_offers in pos_buckets.items():
        p_total = len(pos_offers)
        p_accepted = sum(1 for o in pos_offers if o.get("status", "").lower() == "accepted")
        p_declined = sum(1 for o in pos_offers if o.get("status", "").lower() == "declined")
        p_pending = p_total - p_accepted - p_declined
        p_rate = p_accepted / p_total if p_total else 0.0

        p_days = [float(o["days_to_respond"]) for o in pos_offers if o.get("days_to_respond") is not None]
        p_sals = [float(o["salary_offered"]) for o in pos_offers if o.get("salary_offered") is not None]
        p_avg_days = sum(p_days) / len(p_days) if p_days else 0.0
        p_avg_sal = sum(p_sals) / len(p_sals) if p_sals else 0.0

        # Decline reason analysis
        decline_reasons = [
            (o.get("decline_reason") or "").lower()
            for o in pos_offers if o.get("status", "").lower() == "declined"
        ]
        top_reasons = [r for r, _ in Counter(decline_reasons).most_common(2) if r]

        by_position.append(PositionOfferStats(
            position=pos,
            total_offers=p_total,
            accepted=p_accepted,
            declined=p_declined,
            pending=p_pending,
            acceptance_rate=p_rate,
            avg_salary_offered=p_avg_sal,
            avg_days_to_respond=p_avg_days,
            top_decline_reasons=top_reasons,
        ))

        if p_rate < _LOW_ACCEPTANCE_THRESHOLD and p_total >= 3:
            declining_positions.append(pos)

        # Flag salary-related declines
        if any(any(kw in r for kw in _SALARY_DECLINE_KEYWORDS) for r in decline_reasons):
            salary_flags.append(f"{pos}: salary cited in decline reasons")

    return OfferReport(
        total_offers=total,
        accepted=accepted,
        declined=declined,
        pending=pending,
        overall_acceptance_rate=accepted / total if total else 0.0,
        avg_days_to_respond=avg_days,
        avg_salary_offered=avg_sal,
        by_position=by_position,
        declining_positions=declining_positions,
        salary_flags=salary_flags,
        data_quality="ok",
    )
