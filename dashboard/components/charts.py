"""
Plotly chart helpers for the Reports page.

Each function accepts plain dicts/lists (the same shapes the agents produce)
and returns a plotly Figure ready for st.plotly_chart().
"""
from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go


# ── Pipeline Health ───────────────────────────────────────────────────────────

def pipeline_funnel(stages: list[dict[str, Any]]) -> go.Figure:
    """Funnel chart: candidate count at each pipeline stage."""
    from collections import Counter
    counts = Counter(s.get("stage", "Unknown") for s in stages)
    stage_order = [
        "Application Review", "Phone Screen", "Technical Interview",
        "Final Interview", "Offer", "Hired",
    ]
    labels, values = [], []
    for stage in stage_order:
        if stage in counts:
            labels.append(stage)
            values.append(counts[stage])
    # include any extra stages not in the default order
    for stage, cnt in counts.items():
        if stage not in stage_order:
            labels.append(stage)
            values.append(cnt)

    fig = go.Figure(go.Funnel(
        y=labels, x=values,
        textposition="inside", textinfo="value+percent initial",
        marker={"color": px.colors.sequential.Blues_r[:len(labels)]},
    ))
    fig.update_layout(title="Candidate Pipeline Funnel", height=400)
    return fig


def avg_days_per_stage(stages: list[dict[str, Any]]) -> go.Figure:
    """Horizontal bar chart: average days spent in each stage."""
    from collections import defaultdict
    totals: dict[str, list[float]] = defaultdict(list)
    for s in stages:
        stage = s.get("stage", "Unknown")
        days = float(s.get("days_in_stage", 0))
        totals[stage].append(days)

    labels = list(totals.keys())
    avgs   = [sum(v) / len(v) for v in totals.values()]

    fig = px.bar(
        x=avgs, y=labels, orientation="h",
        labels={"x": "Avg Days", "y": "Stage"},
        title="Average Time per Stage",
        color=avgs,
        color_continuous_scale="Reds",
    )
    fig.update_layout(coloraxis_showscale=False, height=350)
    return fig


# ── Sourcing Quality ──────────────────────────────────────────────────────────

def channel_hire_rate(candidates: list[dict[str, Any]]) -> go.Figure:
    """Bar chart: hire rate per sourcing channel."""
    from collections import defaultdict
    totals:  dict[str, int] = defaultdict(int)
    hires:   dict[str, int] = defaultdict(int)
    for c in candidates:
        ch = c.get("source_channel", "Unknown")
        totals[ch] += 1
        if c.get("hired"):
            hires[ch] += 1

    channels   = list(totals.keys())
    hire_rates = [round(hires[ch] / totals[ch] * 100, 1) if totals[ch] else 0 for ch in channels]

    fig = px.bar(
        x=channels, y=hire_rates,
        labels={"x": "Source Channel", "y": "Hire Rate (%)"},
        title="Hire Rate by Sourcing Channel",
        color=hire_rates,
        color_continuous_scale="Greens",
    )
    fig.update_layout(coloraxis_showscale=False, height=350)
    return fig


def channel_quality_scatter(candidates: list[dict[str, Any]]) -> go.Figure:
    """Scatter: quality score vs volume per channel."""
    from collections import defaultdict
    totals:  dict[str, int] = defaultdict(int)
    quality: dict[str, list[float]] = defaultdict(list)
    for c in candidates:
        ch = c.get("source_channel", "Unknown")
        totals[ch] += 1
        q = c.get("quality_score")
        if q is not None:
            quality[ch].append(float(q))

    channels  = list(totals.keys())
    volumes   = [totals[ch] for ch in channels]
    avg_quals = [round(sum(quality[ch]) / len(quality[ch]), 2) if quality[ch] else 0 for ch in channels]

    fig = px.scatter(
        x=volumes, y=avg_quals, text=channels,
        labels={"x": "Volume (candidates)", "y": "Avg Quality Score"},
        title="Channel Quality vs Volume",
        size=volumes,
        color=avg_quals,
        color_continuous_scale="Teal",
    )
    fig.update_traces(textposition="top center")
    fig.update_layout(coloraxis_showscale=False, height=380)
    return fig


# ── Interviewer Workload ──────────────────────────────────────────────────────

def interviewer_workload_bar(interviewers: list[dict[str, Any]], overload_threshold: int = 15) -> go.Figure:
    """Bar chart: interviews assigned per interviewer (red = overloaded)."""
    names  = [i.get("name", i.get("interviewer_id", "?")) for i in interviewers]
    counts = [int(i.get("interviews_assigned", 0)) for i in interviewers]
    colors = ["crimson" if c > overload_threshold else "steelblue" for c in counts]

    fig = go.Figure(go.Bar(
        x=names, y=counts,
        marker_color=colors,
        text=counts, textposition="outside",
    ))
    fig.add_hline(y=overload_threshold, line_dash="dash", line_color="red",
                  annotation_text=f"Overload threshold ({overload_threshold})")
    fig.update_layout(
        title="Interview Assignments per Interviewer",
        xaxis_title="Interviewer", yaxis_title="Interviews Assigned",
        height=380,
    )
    return fig


def interviewer_rating_bar(interviewers: list[dict[str, Any]]) -> go.Figure:
    """Horizontal bar: avg rating per interviewer."""
    names   = [i.get("name", i.get("interviewer_id", "?")) for i in interviewers]
    ratings = [float(i.get("avg_rating", 0)) for i in interviewers]

    fig = px.bar(
        x=ratings, y=names, orientation="h",
        labels={"x": "Avg Rating (out of 5)", "y": "Interviewer"},
        title="Interviewer Average Ratings",
        color=ratings,
        color_continuous_scale="RdYlGn",
        range_color=[1, 5],
    )
    fig.update_layout(coloraxis_showscale=True, height=350)
    return fig


# ── Offer Insights ────────────────────────────────────────────────────────────

def offer_acceptance_pie(offers: list[dict[str, Any]]) -> go.Figure:
    """Pie chart: accepted vs declined offers."""
    accepted = sum(1 for o in offers if o.get("accepted"))
    declined = len(offers) - accepted
    fig = go.Figure(go.Pie(
        labels=["Accepted", "Declined"],
        values=[accepted, declined],
        marker_colors=["#2ecc71", "#e74c3c"],
        hole=0.4,
    ))
    fig.update_layout(title="Offer Acceptance Overview", height=350)
    return fig


def offer_acceptance_by_position(offers: list[dict[str, Any]]) -> go.Figure:
    """Bar chart: acceptance rate per position."""
    from collections import defaultdict
    totals:   dict[str, int] = defaultdict(int)
    accepted: dict[str, int] = defaultdict(int)
    for o in offers:
        pos = o.get("position", "Unknown")
        totals[pos] += 1
        if o.get("accepted"):
            accepted[pos] += 1

    positions = list(totals.keys())
    rates     = [round(accepted[p] / totals[p] * 100, 1) if totals[p] else 0 for p in positions]

    fig = px.bar(
        x=positions, y=rates,
        labels={"x": "Position", "y": "Acceptance Rate (%)"},
        title="Offer Acceptance Rate by Position",
        color=rates,
        color_continuous_scale="Blues",
    )
    fig.update_layout(coloraxis_showscale=False, height=350)
    return fig


# ── Aggregated chart functions (live PostgreSQL data from /api/v1/metrics/live) ──
# Input shapes come from metrics.py _build_metrics_payload() — pre-aggregated,
# so these functions do NO grouping/counting themselves.

def pipeline_funnel_agg(funnel: list[dict[str, Any]]) -> go.Figure:
    """Funnel chart using pre-aggregated entered counts per stage."""
    labels = [f["stage"]   for f in funnel]
    values = [f["entered"] for f in funnel]
    fig = go.Figure(go.Funnel(
        y=labels, x=values,
        textposition="inside",
        textinfo="value+percent initial",
        marker={"color": px.colors.sequential.Blues_r[:max(len(labels), 1)]},
    ))
    fig.update_layout(title="Candidate Pipeline Funnel", height=420)
    return fig


def avg_days_bar_agg(funnel: list[dict[str, Any]]) -> go.Figure:
    """Horizontal bar: average days in each stage."""
    labels = [f["stage"]    for f in funnel]
    avgs   = [f["avg_days"] for f in funnel]
    fig = px.bar(
        x=avgs, y=labels, orientation="h",
        labels={"x": "Avg Days", "y": "Stage"},
        title="Average Time per Stage (days)",
        color=avgs, color_continuous_scale="Reds",
    )
    fig.update_layout(coloraxis_showscale=False, height=350)
    return fig


def stage_conversion_bar(funnel: list[dict[str, Any]]) -> go.Figure:
    """Bar chart: conversion rate (% that passed) at each stage."""
    labels = [f["stage"]          for f in funnel]
    rates  = [f["conversion_pct"] for f in funnel]
    colors = ["crimson" if r < 50 else "steelblue" for r in rates]
    fig = go.Figure(go.Bar(
        x=labels, y=rates,
        marker_color=colors,
        text=[f"{r}%" for r in rates],
        textposition="outside",
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="gray",
                  annotation_text="50% threshold")
    fig.update_layout(
        title="Stage Conversion Rates (%)",
        yaxis=dict(range=[0, 110]),
        xaxis_title="Stage", yaxis_title="Conversion %",
        height=350,
    )
    return fig


def channel_hire_rate_agg(channels: list[dict[str, Any]]) -> go.Figure:
    """Bar chart: hire rate % per sourcing channel."""
    names = [c["channel"]       for c in channels]
    rates = [c["hire_rate_pct"] for c in channels]
    fig = px.bar(
        x=names, y=rates,
        labels={"x": "Source Channel", "y": "Hire Rate (%)"},
        title="Hire Rate by Sourcing Channel",
        color=rates, color_continuous_scale="Greens",
    )
    fig.update_layout(coloraxis_showscale=False, height=350)
    return fig


def channel_quality_scatter_agg(channels: list[dict[str, Any]]) -> go.Figure:
    """Scatter: candidate volume vs quality score vs hire rate per channel."""
    names   = [c["channel"]       for c in channels]
    volumes = [c["total"]         for c in channels]
    quality = [c["avg_quality"]   for c in channels]
    rates   = [c["hire_rate_pct"] for c in channels]
    fig = px.scatter(
        x=volumes, y=quality, text=names,
        size=[max(v, 1) for v in volumes],
        color=rates,
        color_continuous_scale="RdYlGn",
        labels={"x": "Volume (candidates)", "y": "Avg Quality Score", "color": "Hire Rate %"},
        title="Channel Quality vs Volume (colour = hire rate)",
    )
    fig.update_traces(textposition="top center")
    fig.update_layout(height=380)
    return fig


def interviewer_passrate_bar(interviewers: list[dict[str, Any]]) -> go.Figure:
    """Horizontal bar: interview pass rate per interviewer."""
    names = [i["name"]          for i in interviewers]
    rates = [i["pass_rate_pct"] for i in interviewers]
    fig = px.bar(
        x=rates, y=names, orientation="h",
        labels={"x": "Pass Rate (%)", "y": "Interviewer"},
        title="Interviewer Pass Rate (%)",
        color=rates,
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
    )
    fig.update_layout(coloraxis_showscale=True, height=350)
    return fig


def offer_acceptance_pie_agg(offer_summary: dict[str, Any]) -> go.Figure:
    """Donut chart: accepted / declined / pending offer breakdown."""
    accepted = offer_summary.get("accepted", 0)
    declined = offer_summary.get("declined", 0)
    pending  = offer_summary.get("pending",  0)
    fig = go.Figure(go.Pie(
        labels=["Accepted", "Declined", "Pending"],
        values=[accepted, declined, pending],
        marker_colors=["#2ecc71", "#e74c3c", "#f39c12"],
        hole=0.4,
    ))
    fig.update_layout(title="Offer Acceptance Overview", height=350)
    return fig


def offer_acceptance_by_position_agg(by_position: list[dict[str, Any]]) -> go.Figure:
    """Bar chart: acceptance rate % per position."""
    positions = [p["position"] for p in by_position]
    rates     = [p["rate_pct"] for p in by_position]
    fig = px.bar(
        x=positions, y=rates,
        labels={"x": "Position", "y": "Acceptance Rate (%)"},
        title="Offer Acceptance Rate by Position",
        color=rates, color_continuous_scale="Blues",
    )
    fig.update_layout(coloraxis_showscale=False, height=350)
    return fig


def offer_decline_reasons_bar(decline_reasons: dict[str, int]) -> go.Figure:
    """Horizontal bar: offer decline reason breakdown."""
    if not decline_reasons:
        fig = go.Figure()
        fig.update_layout(title="No decline reason data", height=250)
        return fig
    reasons = list(decline_reasons.keys())
    counts  = [decline_reasons[r] for r in reasons]
    fig = px.bar(
        x=counts, y=reasons, orientation="h",
        labels={"x": "Count", "y": "Reason"},
        title="Offer Decline Reasons",
        color=counts, color_continuous_scale="Reds",
    )
    fig.update_layout(coloraxis_showscale=False, height=max(250, len(reasons) * 55))
    return fig
