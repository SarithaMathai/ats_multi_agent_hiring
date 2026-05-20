"""
Page 2 — Reports: Stakeholder Hiring Dashboard

Three tabs driven by real data:

  Tab 1  Live Metrics      — KPI cards + 8 Plotly charts from live PostgreSQL data.
                             Refreshed on page load (60-second cache).

  Tab 2  AI Analysis       — Full agent report from a selected past run.
                             Pick a scenario or any historical run to see
                             per-agent insights, confidence scores,
                             prioritised recommendations, and RAG evidence.

  Tab 3  Run History       — Timeline of every completed analysis run.
                             Filterable by scenario.  Expandable rows show
                             the full agent breakdown for any historical run.
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st

from dashboard.api_client import api_client
from dashboard.config import SCENARIO_LABELS
from dashboard.components.charts import (
    # Aggregated (live PostgreSQL) chart functions
    pipeline_funnel_agg,
    avg_days_bar_agg,
    stage_conversion_bar,
    channel_hire_rate_agg,
    channel_quality_scatter_agg,
    interviewer_workload_bar,
    interviewer_passrate_bar,
    offer_acceptance_pie_agg,
    offer_acceptance_by_position_agg,
    offer_decline_reasons_bar,
)

st.set_page_config(page_title="Reports | ATS Insights", layout="wide", page_icon="📊")
st.title("📊 Reports")
st.caption(
    "Live metrics from PostgreSQL · AI insights from agent runs · "
    "Full run history — all in one place."
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_PRIORITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
_EFFORT_LABEL  = {"low": "Quick win", "medium": "Medium effort", "high": "Major project"}

_AGENT_EMOJI = {
    "pipeline_health":       "📊",
    "sourcing_quality":      "🔍",
    "improvement_action":    "🔧",
    "resource_optimization": "⚖️",
    "offer_insights":        "💼",
    "evaluation":            "✅",
    "optimization":          "💡",
    "routing":               "🧭",
}

_CONF_COLOR = {
    "high":   "#2ecc71",   # green  ≥ 0.75
    "medium": "#f39c12",   # amber  ≥ 0.50
    "low":    "#e74c3c",   # red    < 0.50
}


def _conf_badge(score: float) -> str:
    if score >= 0.75:
        tier, label = "high",   f"{score:.0%} High"
    elif score >= 0.50:
        tier, label = "medium", f"{score:.0%} Medium"
    else:
        tier, label = "low",    f"{score:.0%} Low"
    color = _CONF_COLOR[tier]
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8em;font-weight:bold">{label}</span>'
    )


def _render_agent_section(agent: dict) -> None:
    """Render one agent's insights + recommendations inside an expander."""
    name   = agent.get("agent_name", "unknown")
    emoji  = _AGENT_EMOJI.get(name, "🤖")
    status = agent.get("status", "")
    score  = agent.get("confidence_score", 0.0)

    if status == "skipped":
        return
    if status == "error":
        st.warning(f"{emoji} **{name.replace('_',' ').title()}** — error: "
                   f"{agent.get('metadata', {}).get('error', 'unknown')}")
        return

    label = f"{emoji} {name.replace('_', ' ').title()}"
    with st.expander(label, expanded=True):
        st.markdown(_conf_badge(score), unsafe_allow_html=True)
        st.write("")

        insights = agent.get("insights", [])
        if insights:
            st.markdown("**Key Findings**")
            for ins in insights:
                st.markdown(f"- {ins}")

        recs = agent.get("recommendations", [])
        if recs:
            st.markdown("**Recommendations**")
            for rec in recs:
                icon   = _PRIORITY_ICON.get(rec.get("priority", "medium"), "⚪")
                effort = _EFFORT_LABEL.get(rec.get("effort", "medium"), "")
                st.markdown(
                    f"{icon} **{rec['title']}** ·  "
                    f"<small style='color:grey'>{effort}</small>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"  {rec['description']}")


def _render_run_summary_row(run: dict) -> None:
    """Render a compact horizontal summary row for a run in the History table."""
    ts       = (run.get("timestamp") or "")[:16].replace("T", " ")
    scenario = run.get("scenario") or "free-form"
    sc_label = SCENARIO_LABELS.get(scenario, scenario.replace("_", " ").title())
    query    = (run.get("query") or "")[:70]
    status   = run.get("status", "?")
    agents   = ", ".join(run.get("agents_run", []))
    tokens   = run.get("total_tokens", 0)
    cost     = run.get("total_cost_usd", 0)
    latency  = run.get("total_latency_ms", 0) / 1000

    status_icon = {"success": "✅", "partial": "⚠️", "error": "❌"}.get(status, "❓")

    with st.expander(
        f"{status_icon} **{ts}** · `{sc_label}` · {query}…", expanded=False
    ):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tokens", f"{tokens:,}")
        col2.metric("Cost",   f"${cost:.5f}")
        col3.metric("Latency", f"{latency:.1f} s")
        col4.metric("Status", status.upper())

        st.markdown(f"**Query:** {run.get('query', '')}")
        st.markdown(f"**Agents:** {agents or '—'}")
        summary = run.get("summary", "")
        if summary:
            st.markdown("**Summary**")
            st.info(summary)

        for agent in run.get("agent_outputs", []):
            _render_agent_section(agent)


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs([
    "🔵 Live Metrics",
    "🟢 AI Analysis Report",
    "🟠 Run History",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — LIVE METRICS
# ════════════════════════════════════════════════════════════════════════════════

with tab1:
    col_hdr, col_btn = st.columns([6, 1])
    with col_hdr:
        st.subheader("Current Hiring Health")
        st.caption("Live data from PostgreSQL — refreshed every 60 seconds.")
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh", key="refresh_live"):
            st.cache_data.clear()
            st.rerun()

    @st.cache_data(ttl=60, show_spinner="Fetching live metrics from PostgreSQL…")
    def _load_metrics() -> dict:
        return api_client.get_live_metrics()

    metrics = _load_metrics()

    if not metrics:
        st.error(
            "Could not load live metrics. Make sure the FastAPI server is running "
            "(`poetry run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`)."
        )
        st.stop()

    stats   = metrics.get("summary_stats", {})
    funnel  = metrics.get("funnel", [])
    channels = metrics.get("channels", [])
    ivrs    = metrics.get("interviewers", [])
    offers  = metrics.get("offers", {})

    # ── KPI cards ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Candidates",    stats.get("total_candidates", "—"))
    k2.metric("Overall Hire Rate",   f"{stats.get('overall_hire_rate_pct', 0):.1f}%")
    k3.metric("Avg Time-to-Hire",    f"{stats.get('avg_time_to_hire_days', 0):.1f} days")
    k4.metric("Stuck >14 days",      stats.get("stuck_candidates", "—"),
              delta_color="inverse" if stats.get("stuck_candidates", 0) > 0 else "normal")
    k5.metric("Overloaded Interviewers", stats.get("overloaded_interviewers", "—"),
              delta_color="inverse" if stats.get("overloaded_interviewers", 0) > 0 else "normal")

    st.markdown("---")

    # ── Pipeline section ───────────────────────────────────────────────────────
    st.markdown("#### Pipeline Health")
    if funnel:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(pipeline_funnel_agg(funnel), use_container_width=True)
        with c2:
            st.plotly_chart(avg_days_bar_agg(funnel), use_container_width=True)
        with c3:
            st.plotly_chart(stage_conversion_bar(funnel), use_container_width=True)

        # Stuck candidates alert
        stuck_count = stats.get("stuck_candidates", 0)
        if stuck_count:
            st.warning(
                f"⚠️ **{stuck_count} candidate(s)** have been in the same stage for "
                f"more than 14 days. Consider reaching out or escalating."
            )
    else:
        st.info("No pipeline stage data available.")

    st.markdown("---")

    # ── Sourcing section ───────────────────────────────────────────────────────
    st.markdown("#### Sourcing Quality")
    if channels:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(channel_hire_rate_agg(channels), use_container_width=True)
        with c2:
            st.plotly_chart(channel_quality_scatter_agg(channels), use_container_width=True)

        # Channel summary table
        st.markdown("**Channel Breakdown**")
        st.dataframe(
            [
                {
                    "Channel":       ch["channel"],
                    "Candidates":    ch["total"],
                    "Hired":         ch["hired"],
                    "Hire Rate":     f"{ch['hire_rate_pct']}%",
                    "Avg Quality":   f"{ch['avg_quality']:.2f}",
                }
                for ch in channels
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No candidate channel data available.")

    st.markdown("---")

    # ── Interviewer section ────────────────────────────────────────────────────
    st.markdown("#### Interviewer Workload")
    overload_threshold = st.slider(
        "Overload threshold (interviews)", 5, 30, 15, key="overload_slider"
    )
    if ivrs:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                interviewer_workload_bar(ivrs, overload_threshold),
                use_container_width=True,
            )
        with c2:
            st.plotly_chart(interviewer_passrate_bar(ivrs), use_container_width=True)

        overloaded = [i for i in ivrs if i["interviews_assigned"] > overload_threshold]
        if overloaded:
            names = ", ".join(f"**{i['name']}** ({i['interviews_assigned']})" for i in overloaded)
            st.error(f"⚠️ Interviewers over capacity: {names}")
    else:
        st.info("No interviewer data available.")

    st.markdown("---")

    # ── Offers section ─────────────────────────────────────────────────────────
    st.markdown("#### Offer Insights")
    if offers.get("total", 0):
        o1, o2, o3 = st.columns(3)
        o1.metric("Total Offers",    offers["total"])
        o2.metric("Accepted",        offers["accepted"])
        o3.metric("Pending",         offers["pending"],
                  delta_color="inverse" if offers["pending"] > 5 else "normal")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(offer_acceptance_pie_agg(offers), use_container_width=True)
        with c2:
            st.plotly_chart(
                offer_acceptance_by_position_agg(offers.get("by_position", [])),
                use_container_width=True,
            )
        with c3:
            st.plotly_chart(
                offer_decline_reasons_bar(offers.get("decline_reasons", {})),
                use_container_width=True,
            )
    else:
        st.info("No offer data available.")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — AI ANALYSIS REPORT
# ════════════════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("AI Analysis Report")
    st.caption(
        "Select a past analysis run to read the full agent report — "
        "insights, recommendations, and confidence scores from every specialist agent."
    )

    @st.cache_data(ttl=30, show_spinner=False)
    def _load_history(limit: int, scenario: str | None) -> list[dict]:
        return api_client.get_run_history(limit=limit, scenario=scenario)

    # Scenario filter
    all_scenarios = ["All scenarios"] + list(SCENARIO_LABELS.keys()) + ["free-form"]
    selected_sc = st.selectbox(
        "Filter by scenario",
        all_scenarios,
        format_func=lambda s: SCENARIO_LABELS.get(s, s.replace("_", " ").title()),
        key="ai_scenario_filter",
    )
    sc_param = None if selected_sc == "All scenarios" else (
        None if selected_sc == "free-form" else selected_sc
    )

    history = _load_history(limit=50, scenario=sc_param)

    if not history:
        st.info(
            "No analysis runs found for this filter. "
            "Run a query on the **Analysis** page first."
        )
    else:
        # Build a human-readable label for each run
        def _run_label(r: dict) -> str:
            ts  = (r.get("timestamp") or "")[:16].replace("T", " ")
            sc  = SCENARIO_LABELS.get(r.get("scenario") or "", r.get("scenario") or "free-form")
            qry = (r.get("query") or "")[:55]
            return f"{ts} | {sc} | {qry}"

        run_options = {_run_label(r): r for r in history}
        selected_label = st.selectbox(
            "Select run", list(run_options.keys()), key="ai_run_selector"
        )
        run = run_options[selected_label]

        # ── Run header ──────────────────────────────────────────────────────────
        st.markdown("---")
        sc_display = SCENARIO_LABELS.get(run.get("scenario") or "", run.get("scenario") or "free-form")
        status_icon = {"success": "✅", "partial": "⚠️", "error": "❌"}.get(run.get("status", ""), "❓")

        hc1, hc2, hc3, hc4 = st.columns(4)
        hc1.metric("Scenario",  sc_display)
        hc2.metric("Status",    f"{status_icon} {run.get('status', '?').upper()}")
        hc3.metric("Tokens",    f"{run.get('total_tokens', 0):,}")
        hc4.metric("Cost",      f"${run.get('total_cost_usd', 0):.5f}")

        st.markdown(f"**Query:** {run.get('query', '')}")
        st.markdown(
            f"**Run ID:** `{run.get('run_id', '')}` &nbsp;·&nbsp; "
            f"**Agents:** {', '.join(run.get('agents_run', []))}"
        )
        st.markdown("---")

        # ── Executive summary ──────────────────────────────────────────────────
        summary = run.get("summary", "")
        if summary:
            st.markdown("#### Executive Summary")
            st.info(summary)
            st.markdown("---")

        # ── Top recommendations across all agents ──────────────────────────────
        all_recs = run.get("all_recommendations", [])
        if all_recs:
            st.markdown("#### Top Recommendations")
            for rec in all_recs[:6]:
                icon   = _PRIORITY_ICON.get(rec.get("priority", "medium"), "⚪")
                effort = _EFFORT_LABEL.get(rec.get("effort", "medium"), "")
                st.markdown(
                    f"{icon} **{rec['title']}** "
                    f"<small style='color:grey'>— {effort}</small>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"&nbsp;&nbsp;&nbsp;{rec['description']}")
            st.markdown("---")

        # ── Per-agent deep dive ────────────────────────────────────────────────
        st.markdown("#### Agent Analysis")
        insight_agents = [
            a for a in run.get("agent_outputs", [])
            if a.get("agent_name") not in ("routing", "evaluation", "optimization")
            and a.get("status") != "skipped"
        ]
        support_agents = [
            a for a in run.get("agent_outputs", [])
            if a.get("agent_name") in ("evaluation", "optimization")
            and a.get("status") != "skipped"
        ]

        for agent in insight_agents:
            _render_agent_section(agent)

        if support_agents:
            st.markdown("#### Quality & Cost Analysis")
            for agent in support_agents:
                _render_agent_section(agent)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — RUN HISTORY
# ════════════════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("Run History")
    st.caption("Every completed pipeline run — newest first.")

    # Controls
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        hist_scenario = st.selectbox(
            "Filter by scenario",
            ["All"] + list(SCENARIO_LABELS.keys()) + ["free-form"],
            format_func=lambda s: "All scenarios" if s == "All"
                else SCENARIO_LABELS.get(s, s.replace("_", " ").title()),
            key="hist_scenario_filter",
        )
    with fc2:
        hist_limit = st.selectbox("Show last N runs", [25, 50, 100], index=0,
                                  key="hist_limit")
    with fc3:
        st.write("")
        if st.button("🔄 Refresh", key="refresh_history"):
            st.cache_data.clear()
            st.rerun()

    @st.cache_data(ttl=30, show_spinner="Loading run history…")
    def _load_hist(limit: int, scenario: str | None) -> list[dict]:
        return api_client.get_run_history(limit=limit, scenario=scenario)

    sc_param_hist = None if hist_scenario == "All" else (
        None if hist_scenario == "free-form" else hist_scenario
    )
    history_all = _load_hist(limit=hist_limit, scenario=sc_param_hist)

    if not history_all:
        st.info(
            "No runs in history yet. Run a query on the **Analysis** page "
            "and it will appear here automatically."
        )
    else:
        # Summary statistics across all loaded runs
        total_tokens_all = sum(r.get("total_tokens", 0) for r in history_all)
        total_cost_all   = sum(r.get("total_cost_usd", 0) for r in history_all)
        success_count    = sum(1 for r in history_all if r.get("status") == "success")

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Runs shown",    len(history_all))
        sc2.metric("Successful",    success_count)
        sc3.metric("Total Tokens",  f"{total_tokens_all:,}")
        sc4.metric("Total Cost",    f"${total_cost_all:.4f}")

        # Scenario usage breakdown
        from collections import Counter
        sc_counts = Counter(
            SCENARIO_LABELS.get(r.get("scenario") or "", r.get("scenario") or "free-form")
            for r in history_all
        )
        sc_str = " · ".join(f"**{k}** {v}×" for k, v in sc_counts.most_common())
        if sc_str:
            st.markdown(f"Scenario mix: {sc_str}")

        st.markdown("---")

        # Expandable rows, one per run
        for run in history_all:
            _render_run_summary_row(run)
