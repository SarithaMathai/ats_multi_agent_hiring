"""
Page 1 — Analysis: Prompt + Response Viewer

Enter a plain-English hiring question, optionally pick a scenario,
hit Run, and watch each agent's output rendered in expandable sections.
Results are stored in st.session_state["last_response"] so the Email page
can read them without re-running.
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st

from dashboard.api_client import api_client
from dashboard.config import DEPARTMENTS, POSITIONS, SCENARIO_LABELS, SCENARIOS, SOURCE_CHANNELS

st.set_page_config(page_title="Analysis | ATS Insights", layout="wide", page_icon="🔍")
st.title("🔍 Analysis")
st.caption("Ask a hiring question in plain English. The multi-agent system will analyse and respond.")

# ── Input form ────────────────────────────────────────────────────────────────

query = st.text_area(
    "Your question",
    height=100,
    placeholder=(
        "e.g. Why is our technical interview stage taking so long?\n"
        "e.g. Which sourcing channels bring in the highest-quality candidates?"
    ),
)

col_s, col_blank = st.columns([2, 3])
with col_s:
    scenario_choice = st.selectbox(
        "Scenario (optional)",
        options=["auto — let the system decide"] + SCENARIOS,
        help="Choose a scenario to lock the agent set. Leave on 'auto' for free-form routing.",
    )
scenario = None if scenario_choice.startswith("auto") else scenario_choice

with st.expander("Filters (optional)"):
    col1, col2, col3 = st.columns(3)
    with col1:
        dept = st.multiselect("Department", DEPARTMENTS)
    with col2:
        position = st.multiselect("Position", POSITIONS)
    with col3:
        channel = st.multiselect("Source Channel", SOURCE_CHANNELS)

filters: dict = {}
if dept:      filters["department"]    = dept
if position:  filters["position"]      = position
if channel:   filters["source_channel"] = channel

run_btn = st.button("Run Analysis", type="primary", disabled=not query.strip())

# ── Run & display ─────────────────────────────────────────────────────────────

if run_btn and query.strip():
    with st.spinner("Running agents… this may take 15–60 seconds"):
        response = api_client.run_analysis(query.strip(), scenario, filters)

    st.session_state["last_response"] = response

    status = response.get("status", "error")
    latency = response.get("total_latency_ms", 0)
    tokens  = response.get("total_tokens", 0)
    run_id  = response.get("run_id", "n/a")

    # ── Status banner
    if status == "success":
        st.success(f"Completed in {latency:.0f} ms · {tokens:,} tokens · run_id: {run_id}")
    elif status in ("partial", "partial_success"):
        st.warning(f"Partial success in {latency:.0f} ms · {tokens:,} tokens · run_id: {run_id}")
    else:
        st.error(f"Pipeline returned status: {status}")

    # ── Summary
    summary = response.get("summary", "")
    if summary:
        with st.expander("📋 Summary", expanded=True):
            st.markdown(summary)

    # ── Top recommendations
    recs = response.get("all_recommendations", [])
    if recs:
        st.subheader("Top Recommendations")
        priority_colors = {"high": "🔴", "medium": "🟡", "low": "🔵"}
        for rec in recs[:6]:
            p    = rec.get("priority", "medium")
            icon = priority_colors.get(p, "⚪")
            with st.expander(f"{icon} [{p.upper()}] {rec.get('title', '')}"):
                st.write(rec.get("description", ""))
                if rec.get("effort"):
                    st.caption(f"Effort: {rec['effort']}")

    # ── Per-agent outputs
    st.subheader("Agent Outputs")
    skip_agents = {"routing"}
    for out in response.get("agent_outputs", []):
        name   = out.get("agent_name", "unknown")
        status_a = out.get("status", "unknown")
        conf   = out.get("confidence_score", 0.0)

        if name in skip_agents or status_a == "skipped":
            continue

        conf_color = "green" if conf >= 0.75 else "orange" if conf >= 0.5 else "red"
        label = f"🤖 {name.replace('_',' ').title()} — :{conf_color}[confidence {conf:.0%}] — status: {status_a}"

        with st.expander(label):
            insights = out.get("insights", [])
            if insights:
                st.markdown("**Insights**")
                for insight in insights:
                    st.markdown(f"- {insight}")

            agent_recs = out.get("recommendations", [])
            if agent_recs:
                st.markdown("**Recommendations**")
                for rec in agent_recs:
                    st.info(f"**{rec.get('title','')}** — {rec.get('description','')}")

            evidence = out.get("evidence", [])
            if evidence:
                with st.expander("Evidence"):
                    st.json(evidence)

            meta = out.get("metadata", {})
            if meta:
                with st.expander("Metadata"):
                    st.json(meta)

    st.caption("💡 Go to **Email Stakeholders** to send this report to your team.")

elif "last_response" in st.session_state and not run_btn:
    st.info("Showing last run result. Click **Run Analysis** to refresh.")
