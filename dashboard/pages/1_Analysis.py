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

# ── Agent profile: known data sources per agent ───────────────────────────────
# structured  → human-readable names of the DB tables / keys each agent reads
# rag         → ChromaDB collection names queried via RAG
# role        → one-line description of the agent's job
# emoji       → icon used in the workflow diagram

_AGENT_PROFILE = {
    "routing": {
        "emoji": "🧭", "role": "Classifies query → selects specialist agents",
        "structured": [], "rag": [],
    },
    "pipeline_health": {
        "emoji": "📊", "role": "Stage bottlenecks, conversion rates, stuck candidates",
        "structured": ["stages (time-in-stage, pass/fail per candidate)"],
        "rag": ["ats_feedback"],
    },
    "sourcing_quality": {
        "emoji": "🔍", "role": "Channel effectiveness, hire rates, quality scores",
        "structured": ["candidates (source_channel, quality_score, hired)"],
        "rag": ["ats_resumes", "ats_candidates"],
    },
    "improvement_action": {
        "emoji": "🔧", "role": "Rejection patterns, bias detection, process redesign",
        "structured": ["rejections (stage, rejection_category)"],
        "rag": ["ats_interventions"],
    },
    "resource_optimization": {
        "emoji": "⚖️", "role": "Interviewer workload, scheduling, capacity planning",
        "structured": ["interviewers (interviews_assigned, avg_rating)"],
        "rag": ["ats_feedback"],
    },
    "offer_insights": {
        "emoji": "💼", "role": "Offer acceptance, compensation benchmarking, decline reasons",
        "structured": ["offers (position, accepted, decline_reason)"],
        "rag": ["ats_candidates"],
    },
    "evaluation": {
        "emoji": "✅", "role": "Quality check — validates evidence, flags weak claims",
        "structured": ["All insight agent outputs (insights, confidence scores, recommendations)"],
        "rag": [],
    },
    "optimization": {
        "emoji": "⚡", "role": "Cost and performance optimization recommendations",
        "structured": ["Token usage, latency (ms), estimated cost per agent"],
        "rag": [],
    },
}

_INSIGHT_AGENTS  = {"pipeline_health", "sourcing_quality", "improvement_action",
                    "resource_optimization", "offer_insights"}
_SUPPORT_AGENTS  = {"evaluation", "optimization"}
_CONF_COLOR      = lambda c: "green" if c >= 0.75 else "orange" if c >= 0.5 else "red"

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

# ── Fetch on button click only ────────────────────────────────────────────────

if run_btn and query.strip():
    with st.spinner("Running agents… this may take 15–60 seconds"):
        st.session_state["last_response"] = api_client.run_analysis(
            query.strip(), scenario, filters
        )

if "last_response" not in st.session_state:
    st.stop()

response = st.session_state["last_response"]

if not run_btn:
    st.info("Showing last run result. Click **Run Analysis** to refresh.")

# ── Status banner ─────────────────────────────────────────────────────────────

status  = response.get("status", "error")
latency = response.get("total_latency_ms", 0)
tokens  = response.get("total_tokens", 0)
run_id  = response.get("run_id", "n/a")

if status == "success":
    st.success(f"Completed in {latency:.0f} ms · {tokens:,} tokens · run_id: {run_id}")
elif status in ("partial", "partial_success"):
    st.warning(f"Partial success in {latency:.0f} ms · {tokens:,} tokens · run_id: {run_id}")
else:
    st.error(f"Pipeline returned status: {status}")

# ── Summary ───────────────────────────────────────────────────────────────────

summary = response.get("summary", "")
if summary:
    with st.expander("📋 Summary", expanded=True):
        st.markdown(summary)

# ── Top recommendations ───────────────────────────────────────────────────────

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

# ── Helpers ───────────────────────────────────────────────────────────────────

def _agent_card(out: dict) -> None:
    """Render a compact agent card for the orchestration diagram."""
    name    = out.get("agent_name", "unknown")
    conf    = out.get("confidence_score", 0.0)
    status_ = out.get("status", "unknown")
    lat     = out.get("latency_ms", 0.0)
    tok     = (out.get("token_usage") or {})
    profile = _AGENT_PROFILE.get(name, {"emoji": "🤖", "role": "", "structured": [], "rag": []})

    status_icon = "✅" if status_ == "success" else ("⚠️" if status_ == "skipped" else "❌")
    color       = _CONF_COLOR(conf)

    with st.container(border=True):
        st.markdown(f"**{profile['emoji']} {name.replace('_', ' ').title()}** {status_icon}")
        st.caption(profile["role"])
        if status_ == "success":
            st.markdown(f":{color}[**Confidence: {conf:.0%}**]")
        cols = st.columns(2)
        cols[0].caption(f"⏱ {lat:.0f} ms")
        total_tok = (tok.get("input_tokens", 0) or 0) + (tok.get("output_tokens", 0) or 0)
        cols[1].caption(f"🪙 {total_tok:,} tokens")

        if profile["structured"]:
            st.markdown("**📋 Structured data:**")
            for s in profile["structured"]:
                st.caption(f"• {s}")
        if profile["rag"]:
            st.markdown("**📚 RAG collections:**")
            for r in profile["rag"]:
                st.caption(f"• `{r}`")


def _arrow_col(col) -> None:
    col.markdown("<div style='text-align:center;font-size:2rem;padding-top:3rem'>→</div>",
                 unsafe_allow_html=True)


# ── Workflow Orchestration ────────────────────────────────────────────────────

st.markdown("---")
st.subheader("🔄 Workflow Orchestration")
st.caption("Complete execution pipeline — agents called in order, data sources used, confidence score per agent")

all_outputs    = response.get("agent_outputs", [])
by_name        = {o["agent_name"]: o for o in all_outputs}
routing_out    = by_name.get("routing")
insight_outs   = [o for o in all_outputs if o["agent_name"] in _INSIGHT_AGENTS
                  and o.get("status") != "skipped"]
support_outs   = [o for o in all_outputs if o["agent_name"] in _SUPPORT_AGENTS
                  and o.get("status") != "skipped"]

# Column widths: routing | arrow | insights | arrow | support
col_widths = [2, 0.4, max(len(insight_outs), 1) * 1.8, 0.4, 2.5]
cols = st.columns(col_widths)

# Stage 1 — Routing
with cols[0]:
    st.markdown("##### Stage 1\n**Routing**")
    if routing_out and routing_out.get("status") != "skipped":
        _agent_card(routing_out)
        meta = routing_out.get("metadata", {})
        selected = meta.get("selected_agents", [])
        mode     = meta.get("routing_mode", "llm")
        if selected:
            st.caption(f"Mode: `{mode}` → selected **{len(selected)}** agent(s)")
    else:
        with st.container(border=True):
            st.markdown("**🧭 Routing** ⏭️")
            meta = (routing_out or {}).get("metadata", {})
            forced = meta.get("selected_agents", [])
            st.caption(f"Skipped — forced agents: {', '.join(forced) or 'none'}")

_arrow_col(cols[1])

# Stage 2 — Insight Agents (parallel)
with cols[2]:
    n = len(insight_outs)
    st.markdown(f"##### Stage 2\n**Insight Agents** *(parallel · {n} active)*")
    if insight_outs:
        sub_cols = st.columns(n)
        for i, out in enumerate(insight_outs):
            with sub_cols[i]:
                _agent_card(out)
    else:
        st.info("No insight agents ran.")

_arrow_col(cols[3])

# Stage 3 — Support Agents (sequential: Evaluation → Optimization)
with cols[4]:
    st.markdown("##### Stage 3\n**Support Agents** *(sequential)*")
    for out in support_outs:
        _agent_card(out)
        if out["agent_name"] == "evaluation":
            v = out.get("metadata", {}).get("verification", {})
            if v:
                p, t = v.get("passed", 0), v.get("total_agents", 0)
                flagged = v.get("flagged_agents", [])
                st.caption(f"Passed {p}/{t} agents" +
                           (f" · ⚠️ flagged: {', '.join(flagged)}" if flagged else ""))
        if out["agent_name"] == "optimization":
            c = out.get("metadata", {}).get("cost_summary", {})
            if c:
                st.caption(f"Total: {c.get('total_tokens',0):,} tokens · "
                           f"~${c.get('total_cost_usd',0):.4f} · "
                           f"p95 latency {c.get('p95_latency_ms',0):.0f} ms")

    if not support_outs:
        st.info("No support agents ran.")

st.markdown("---")

# ── Per-agent outputs ─────────────────────────────────────────────────────────

st.subheader("Agent Outputs")
show_routing = st.toggle(
    "Show routing agent",
    value=False,
    help="Shows which agents were selected and why",
)

for out in all_outputs:
    name     = out.get("agent_name", "unknown")
    status_a = out.get("status", "unknown")
    conf     = out.get("confidence_score", 0.0)

    if name == "routing" and not show_routing:
        continue
    if status_a == "skipped":
        continue

    color = _CONF_COLOR(conf)
    label = f"🤖 {name.replace('_',' ').title()} — :{color}[confidence {conf:.0%}] — status: {status_a}"

    with st.expander(label):

        # ── Data Sources ──────────────────────────────────────────────────────
        profile  = _AGENT_PROFILE.get(name, {"structured": [], "rag": []})
        evidence = out.get("evidence", [])

        with st.container(border=True):
            st.markdown("**🗂️ Data Sources used to derive recommendations**")

            ds_col1, ds_col2 = st.columns(2)

            with ds_col1:
                st.markdown("📋 **Structured Data**")
                if profile["structured"]:
                    for s in profile["structured"]:
                        st.markdown(f"- {s}")
                else:
                    st.caption("None — uses previous agent outputs only")

            with ds_col2:
                st.markdown("📚 **Unstructured Data (ChromaDB / RAG)**")
                if evidence:
                    # Group evidence by collection
                    by_col: dict[str, list] = {}
                    for ev in evidence:
                        col_name = ev.get("collection") or "unknown"
                        by_col.setdefault(col_name, []).append(ev)
                    for col_name, chunks in by_col.items():
                        st.markdown(f"**`{col_name}`** — {len(chunks)} chunk(s) retrieved")
                        for ch in chunks[:2]:  # show first 2 excerpts
                            score = ch.get("relevance_score", 0.0)
                            excerpt = (ch.get("excerpt") or "")[:120]
                            st.caption(f"↳ relevance {score:.2f}: *{excerpt}…*")
                elif profile["rag"]:
                    st.caption(f"Collections queried: {', '.join(f'`{r}`' for r in profile['rag'])}")
                    st.caption("No chunks retrieved (ChromaDB may be empty)")
                else:
                    st.caption("None — this agent does not use RAG")

        # ── Insights ──────────────────────────────────────────────────────────
        insights = out.get("insights", [])
        if insights:
            st.markdown("**Insights**")
            for insight in insights:
                st.markdown(f"- {insight}")

        # ── Recommendations ───────────────────────────────────────────────────
        agent_recs = out.get("recommendations", [])
        if agent_recs:
            st.markdown("**Recommendations**")
            for rec in agent_recs:
                st.info(f"**{rec.get('title','')}** — {rec.get('description','')}")

        # ── Supporting evidence ───────────────────────────────────────────────
        if evidence:
            with st.expander("Evidence"):
                st.json(evidence)

        # ── Metadata ──────────────────────────────────────────────────────────
        meta = out.get("metadata", {})
        if meta:
            with st.expander("Metadata"):
                st.json(meta)

st.caption("💡 Go to **Email Stakeholders** to send this report to your team.")
