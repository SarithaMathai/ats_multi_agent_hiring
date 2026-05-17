"""
Page 2 — Reports: Pre-Built Visual Reports

Four tabbed dashboards backed by sample or pasted data.
Sidebar lets the user upload CSV files or paste JSON to drive all charts.
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

import json

import streamlit as st

from dashboard.components.charts import (
    avg_days_per_stage,
    channel_hire_rate,
    channel_quality_scatter,
    interviewer_rating_bar,
    interviewer_workload_bar,
    offer_acceptance_by_position,
    offer_acceptance_pie,
    pipeline_funnel,
)

st.set_page_config(page_title="Reports | ATS Insights", layout="wide", page_icon="📊")
st.title("📊 Reports")
st.caption("Visual analytics across all hiring dimensions. Paste sample data or upload CSVs to populate charts.")

# ── Sample data (used when nothing is uploaded) ───────────────────────────────

_SAMPLE_STAGES = [
    {"stage": "Application Review", "candidate_id": f"c{i}", "days_in_stage": d, "passed": True}
    for i, d in enumerate([2, 3, 5, 8, 4, 6, 3, 7])
] + [
    {"stage": "Phone Screen",        "candidate_id": f"c{i+8}",  "days_in_stage": d, "passed": True}
    for i, d in enumerate([5, 4, 6, 3, 7])
] + [
    {"stage": "Technical Interview", "candidate_id": f"c{i+13}", "days_in_stage": d, "passed": p}
    for i, (d, p) in enumerate([(15, False), (20, True), (18, False), (22, True)])
] + [
    {"stage": "Offer", "candidate_id": f"c{i+17}", "days_in_stage": d, "passed": True}
    for i, d in enumerate([3, 4])
]

_SAMPLE_CANDIDATES = [
    {"candidate_id": f"c{i}", "source_channel": ch, "quality_score": q, "hired": h}
    for i, (ch, q, h) in enumerate([
        ("LinkedIn", 0.72, True),  ("LinkedIn",  0.65, False), ("Referral", 0.88, True),
        ("Indeed",   0.45, False), ("LinkedIn",  0.81, True),  ("Referral", 0.91, True),
        ("Indeed",   0.38, False), ("Agency",    0.55, False), ("LinkedIn", 0.70, False),
        ("Referral", 0.85, True),  ("Direct",    0.60, False), ("Agency",   0.48, False),
    ])
]

_SAMPLE_INTERVIEWERS = [
    {"interviewer_id": f"i{i}", "name": n, "interviews_assigned": c, "avg_rating": r}
    for i, (n, c, r) in enumerate([
        ("Alice", 18, 4.5), ("Bob", 7, 4.2), ("Carol", 22, 3.8),
        ("Dave", 4, 4.7), ("Eve", 16, 4.1),
    ])
]

_SAMPLE_OFFERS = [
    {"candidate_id": f"o{i}", "position": pos, "accepted": acc, "decline_reason": dr}
    for i, (pos, acc, dr) in enumerate([
        ("SWE", True, None), ("SWE", False, "compensation"),
        ("PM",  True, None), ("PM",  False, "compensation"),
        ("SWE", True, None), ("DS",  False, "competing offer"),
        ("DS",  True, None), ("SWE", False, "compensation"),
    ])
]


# ── Sidebar data controls ─────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Data Source")
    data_mode = st.radio("Load from", ["Built-in sample data", "Paste JSON"])

    stages_data       = _SAMPLE_STAGES
    candidates_data   = _SAMPLE_CANDIDATES
    interviewers_data = _SAMPLE_INTERVIEWERS
    offers_data       = _SAMPLE_OFFERS

    if data_mode == "Paste JSON":
        raw = st.text_area(
            "Paste JSON (dict with keys: stages, candidates, interviewers, offers)",
            height=200,
            placeholder='{"stages": [...], "candidates": [...], ...}',
        )
        if raw.strip():
            try:
                parsed = json.loads(raw)
                stages_data       = parsed.get("stages",       _SAMPLE_STAGES)
                candidates_data   = parsed.get("candidates",   _SAMPLE_CANDIDATES)
                interviewers_data = parsed.get("interviewers", _SAMPLE_INTERVIEWERS)
                offers_data       = parsed.get("offers",       _SAMPLE_OFFERS)
                st.success("JSON loaded.")
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

    st.markdown("---")
    overload_threshold = st.slider("Overload threshold (interviews/interviewer)", 5, 30, 15)


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "🔵 Pipeline Health",
    "🟢 Sourcing Quality",
    "🟠 Interviewer Workload",
    "🟣 Offer Insights",
])

# ── Tab 1: Pipeline Health ────────────────────────────────────────────────────

with tab1:
    st.subheader("Pipeline Health")
    if not stages_data:
        st.info("No stage data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(pipeline_funnel(stages_data), use_container_width=True)
        with c2:
            st.plotly_chart(avg_days_per_stage(stages_data), use_container_width=True)

        # Stuck candidates table
        stuck = [s for s in stages_data if float(s.get("days_in_stage", 0)) > 14]
        if stuck:
            st.warning(f"{len(stuck)} candidate(s) stuck in stage for >14 days")
            st.dataframe(stuck, use_container_width=True)

# ── Tab 2: Sourcing Quality ───────────────────────────────────────────────────

with tab2:
    st.subheader("Sourcing Quality")
    if not candidates_data:
        st.info("No candidate data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(channel_hire_rate(candidates_data), use_container_width=True)
        with c2:
            st.plotly_chart(channel_quality_scatter(candidates_data), use_container_width=True)

        # Summary table
        from collections import defaultdict
        totals: dict = defaultdict(int)
        hires:  dict = defaultdict(int)
        for c in candidates_data:
            ch = c.get("source_channel", "Unknown")
            totals[ch] += 1
            if c.get("hired"):
                hires[ch] += 1
        rows = [
            {"Channel": ch, "Total": totals[ch], "Hired": hires[ch],
             "Hire Rate": f"{hires[ch]/totals[ch]*100:.1f}%"}
            for ch in totals
        ]
        st.dataframe(rows, use_container_width=True)

# ── Tab 3: Interviewer Workload ───────────────────────────────────────────────

with tab3:
    st.subheader("Interviewer Workload")
    if not interviewers_data:
        st.info("No interviewer data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                interviewer_workload_bar(interviewers_data, overload_threshold),
                use_container_width=True,
            )
        with c2:
            st.plotly_chart(interviewer_rating_bar(interviewers_data), use_container_width=True)

        overloaded = [
            i for i in interviewers_data
            if int(i.get("interviews_assigned", 0)) > overload_threshold
        ]
        if overloaded:
            st.error(f"⚠️ {len(overloaded)} interviewer(s) over capacity (>{overload_threshold} interviews):")
            for iv in overloaded:
                st.markdown(
                    f"- **{iv.get('name', iv.get('interviewer_id'))}** — "
                    f"{iv.get('interviews_assigned')} interviews"
                )

# ── Tab 4: Offer Insights ─────────────────────────────────────────────────────

with tab4:
    st.subheader("Offer Insights")
    if not offers_data:
        st.info("No offer data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(offer_acceptance_pie(offers_data), use_container_width=True)
        with c2:
            st.plotly_chart(offer_acceptance_by_position(offers_data), use_container_width=True)

        # Decline reasons
        reasons = [o.get("decline_reason") for o in offers_data if o.get("decline_reason")]
        if reasons:
            from collections import Counter
            reason_counts = Counter(reasons)
            st.markdown("**Top decline reasons:**")
            for reason, count in reason_counts.most_common(5):
                st.markdown(f"- {reason} ({count}×)")
