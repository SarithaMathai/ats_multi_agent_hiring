"""
Pure-Python channel analysis for sourcing quality.

No LLM, no I/O — computes per-channel statistics from the candidates list
and returns a ChannelReport dataclass + human-readable text for the LLM prompt.

Expected keys in structured_data:
    candidates : list[dict]  — each dict has candidate_id, source_channel,
                               status (hired | rejected | active | withdrawn),
                               stage (optional), quality_score (optional float 0-1)
    jobs       : list[dict]  — optional; used to enrich channel-to-role mapping
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Domain types ─────────────────────────────────────────────────────────────────

@dataclass
class ChannelStats:
    channel: str
    total_candidates: int
    advanced: int        # moved past initial screening
    hired: int
    rejected: int
    withdrawn: int
    quality_score: float         # average candidate quality_score (0–1); 0 if not provided
    hire_rate: float             # hired / total_candidates
    advancement_rate: float      # advanced / total_candidates
    rejection_rate: float        # rejected / total_candidates


@dataclass
class ChannelReport:
    total_candidates: int
    total_channels: int
    channels: list[ChannelStats] = field(default_factory=list)
    top_channel_by_hire_rate: str = ""
    top_channel_by_volume: str = ""
    underperforming_channels: list[str] = field(default_factory=list)   # high vol, low hire rate
    underutilised_channels: list[str] = field(default_factory=list)     # low vol but decent rate
    data_quality: str = "ok"

    def to_text(self) -> str:
        lines: list[str] = [
            f"Total candidates across all channels: {self.total_candidates}",
            f"Distinct source channels: {self.total_channels}",
        ]
        if self.top_channel_by_hire_rate:
            lines.append(f"Highest hire-rate channel: {self.top_channel_by_hire_rate}")
        if self.top_channel_by_volume:
            lines.append(f"Highest volume channel: {self.top_channel_by_volume}")
        if self.underperforming_channels:
            lines.append(f"Underperforming channels (high vol, low hire rate): "
                         f"{', '.join(self.underperforming_channels)}")
        if self.underutilised_channels:
            lines.append(f"Underutilised channels (low vol but good quality): "
                         f"{', '.join(self.underutilised_channels)}")

        if self.channels:
            lines.append("\nPer-channel breakdown:")
            # Sort by total descending so the most relevant rows come first
            for ch in sorted(self.channels, key=lambda c: c.total_candidates, reverse=True):
                qs = f", avg_quality={ch.quality_score:.2f}" if ch.quality_score > 0 else ""
                lines.append(
                    f"  {ch.channel}: total={ch.total_candidates}, "
                    f"hired={ch.hired}, hire_rate={ch.hire_rate:.1%}, "
                    f"advanced={ch.advanced}, adv_rate={ch.advancement_rate:.1%}"
                    f"{qs}"
                )

        if self.data_quality != "ok":
            lines.append(f"\n[Data quality: {self.data_quality}]")

        return "\n".join(lines)


# ── Thresholds ────────────────────────────────────────────────────────────────────

_UNDERPERFORMING_VOLUME_THRESHOLD = 10    # channel considered "high volume"
_UNDERPERFORMING_HIRE_RATE_THRESHOLD = 0.05   # hire rate below 5 % = underperforming
_UNDERUTILISED_VOLUME_THRESHOLD = 5       # fewer than 5 candidates = low volume
_UNDERUTILISED_MIN_QUALITY = 0.65         # quality score > 0.65 = worth scaling

# Statuses that count as "advanced past screening"
_ADVANCED_STATUSES = {"active", "hired", "offer", "interview", "technical"}


# ── Public API ────────────────────────────────────────────────────────────────────

def compute_channel_stats(structured_data: dict[str, Any]) -> ChannelReport:
    """Derive ChannelReport from structured_data supplied by the Coordinator."""
    candidates: list[dict] = structured_data.get("candidates", [])

    if not candidates:
        return ChannelReport(
            total_candidates=0,
            total_channels=0,
            data_quality="missing",
        )

    # Aggregate per channel
    agg: dict[str, dict[str, Any]] = {}
    for c in candidates:
        ch = (c.get("source_channel") or "unknown").strip().lower()
        if ch not in agg:
            agg[ch] = {
                "total": 0, "advanced": 0, "hired": 0,
                "rejected": 0, "withdrawn": 0, "quality_scores": [],
            }
        bucket = agg[ch]
        bucket["total"] += 1

        status = (c.get("status") or "").strip().lower()
        if status == "hired":
            bucket["hired"] += 1
        elif status == "rejected":
            bucket["rejected"] += 1
        elif status == "withdrawn":
            bucket["withdrawn"] += 1

        if status in _ADVANCED_STATUSES:
            bucket["advanced"] += 1

        qs = c.get("quality_score")
        if qs is not None:
            try:
                bucket["quality_scores"].append(float(qs))
            except (TypeError, ValueError):
                pass

    channel_stats: list[ChannelStats] = []
    for ch_name, b in agg.items():
        total = b["total"]
        hired = b["hired"]
        advanced = b["advanced"]
        rejected = b["rejected"]
        withdrawn = b["withdrawn"]
        qs_list = b["quality_scores"]
        avg_qs = sum(qs_list) / len(qs_list) if qs_list else 0.0

        channel_stats.append(ChannelStats(
            channel=ch_name,
            total_candidates=total,
            advanced=advanced,
            hired=hired,
            rejected=rejected,
            withdrawn=withdrawn,
            quality_score=avg_qs,
            hire_rate=hired / total if total > 0 else 0.0,
            advancement_rate=advanced / total if total > 0 else 0.0,
            rejection_rate=rejected / total if total > 0 else 0.0,
        ))

    # Derived aggregates
    underperforming = [
        ch.channel for ch in channel_stats
        if ch.total_candidates >= _UNDERPERFORMING_VOLUME_THRESHOLD
        and ch.hire_rate < _UNDERPERFORMING_HIRE_RATE_THRESHOLD
    ]
    underutilised = [
        ch.channel for ch in channel_stats
        if ch.total_candidates < _UNDERUTILISED_VOLUME_THRESHOLD
        and ch.quality_score >= _UNDERUTILISED_MIN_QUALITY
    ]

    by_hire_rate = max(channel_stats, key=lambda c: c.hire_rate, default=None)
    by_volume = max(channel_stats, key=lambda c: c.total_candidates, default=None)

    return ChannelReport(
        total_candidates=len(candidates),
        total_channels=len(channel_stats),
        channels=channel_stats,
        top_channel_by_hire_rate=by_hire_rate.channel if by_hire_rate else "",
        top_channel_by_volume=by_volume.channel if by_volume else "",
        underperforming_channels=underperforming,
        underutilised_channels=underutilised,
        data_quality="ok" if candidates else "missing",
    )
