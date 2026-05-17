"""
Page 3 — Agent Tester: Run any single agent in isolation.

Calls agents directly via Python imports — FastAPI server does NOT need to
be running.  Useful during development and demos to inspect individual agent
behaviour.
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

import asyncio
import json

import streamlit as st

from shared.constants.agent_names import INSIGHT_AGENTS, SUPPORT_AGENTS

st.set_page_config(page_title="Agent Tester | ATS Insights", layout="wide", page_icon="🧪")
st.title("🧪 Agent Tester")
st.caption(
    "Test any individual agent in isolation. "
    "No FastAPI server required — agents run directly in this process."
)

# ── Sample structured data for each agent ─────────────────────────────────────

_SAMPLE_DATA: dict[str, dict] = {
    "pipeline_health": {
        "stages": [
            {"stage": "Application Review", "candidate_id": f"c{i}", "days_in_stage": d, "passed": True}
            for i, d in enumerate([2, 8, 5, 12, 3, 7])
        ] + [
            {"stage": "Technical Interview", "candidate_id": f"c{i+6}", "days_in_stage": d, "passed": p}
            for i, (d, p) in enumerate([(18, False), (22, True), (15, False)])
        ]
    },
    "sourcing_quality": {
        "candidates": [
            {"candidate_id": f"c{i}", "source_channel": ch, "quality_score": q, "hired": h}
            for i, (ch, q, h) in enumerate([
                ("LinkedIn", 0.72, True), ("Referral", 0.88, True),
                ("Indeed",   0.45, False), ("LinkedIn", 0.65, False),
                ("Agency",   0.55, False), ("Referral", 0.91, True),
            ])
        ]
    },
    "improvement_action": {
        "rejections": [
            {"candidate_id": f"r{i}", "stage": s, "rejection_category": cat}
            for i, (s, cat) in enumerate([
                ("Technical Interview", "technical_skills"),
                ("Phone Screen", "skills_mismatch"),
                ("Technical Interview", "technical_skills"),
                ("Offer", "compensation"),
                ("Phone Screen", "skills_mismatch"),
            ])
        ]
    },
    "resource_optimization": {
        "interviewers": [
            {"interviewer_id": f"i{i}", "name": n, "interviews_assigned": c, "avg_rating": r}
            for i, (n, c, r) in enumerate([
                ("Alice", 18, 4.5), ("Bob", 5, 4.2), ("Carol", 22, 3.8), ("Dave", 3, 4.7),
            ])
        ]
    },
    "offer_insights": {
        "offers": [
            {"candidate_id": f"o{i}", "position": pos, "accepted": acc, "decline_reason": dr}
            for i, (pos, acc, dr) in enumerate([
                ("SWE", True, None), ("SWE", False, "compensation"),
                ("PM",  True, None), ("PM",  False, "compensation"),
                ("DS",  True, None), ("DS",  False, "competing offer"),
            ])
        ]
    },
    "evaluation":    {},
    "optimization":  {},
}

_AGENT_MODULES = {
    "pipeline_health":       ("agents.insight.pipeline_health.pipeline_health_agent",       "PipelineHealthAgent"),
    "sourcing_quality":      ("agents.insight.sourcing_quality.sourcing_quality_agent",      "SourcingQualityAgent"),
    "improvement_action":    ("agents.insight.improvement_action.improvement_action_agent",  "ImprovementActionAgent"),
    "resource_optimization": ("agents.insight.resource_optimization.resource_optimization_agent", "ResourceOptimizationAgent"),
    "offer_insights":        ("agents.insight.offer_insights.offer_insights_agent",          "OfferInsightsAgent"),
    "evaluation":            ("agents.support.evaluation.evaluation_agent",                  "EvaluationAgent"),
    "optimization":          ("agents.support.optimization.optimization_agent",              "OptimizationAgent"),
}

ALL_TESTABLE = INSIGHT_AGENTS + SUPPORT_AGENTS


# ── UI ────────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([1, 2])

with col_left:
    agent_name = st.selectbox("Select agent", ALL_TESTABLE)
    query = st.text_input(
        "Test query",
        value="Which interviewers are overloaded this week?",
        placeholder="Enter a hiring question for this agent...",
    )
    show_raw = st.checkbox("Show raw AgentOutput JSON", value=False)
    use_sample = st.checkbox("Use built-in sample data", value=True)

    custom_data: dict = {}
    if not use_sample:
        raw_data = st.text_area(
            "structured_data (JSON)",
            height=180,
            placeholder='{"stages": [...]}',
        )
        if raw_data.strip():
            try:
                custom_data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

    run_btn = st.button("Test Agent", type="primary")

with col_right:
    if run_btn:
        structured = _SAMPLE_DATA.get(agent_name, {}) if use_sample else custom_data

        module_path, class_name = _AGENT_MODULES[agent_name]

        with st.spinner(f"Running {agent_name}…"):
            try:
                import importlib
                from agents.base.base_agent import AgentContext

                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                agent = cls()

                context = AgentContext(
                    query=query,
                    run_id="tester-001",
                    structured_data=structured,
                    rag_collections=[],
                    filters={},
                )

                output = asyncio.run(agent.run(context))

            except Exception as exc:
                st.error(f"Agent raised an exception: {exc}")
                st.stop()

        # ── Results
        m1, m2, m3 = st.columns(3)
        m1.metric("Status",     output.status)
        m2.metric("Confidence", f"{output.confidence_score:.0%}")
        m3.metric("Tokens",     output.token_usage.total_tokens)

        if show_raw:
            st.json(output.model_dump())
        else:
            if output.insights:
                st.markdown("**Insights**")
                for insight in output.insights:
                    st.markdown(f"- {insight}")

            if output.recommendations:
                st.markdown("**Recommendations**")
                for rec in output.recommendations:
                    st.info(f"**[{rec.priority.upper()}] {rec.title}** — {rec.description}")

            if output.evidence:
                with st.expander("Evidence"):
                    st.json([e.model_dump() for e in output.evidence])

            if output.metadata:
                with st.expander("Metadata"):
                    st.json(output.metadata)

    else:
        st.info("Select an agent and click **Test Agent** to see its output here.")
        st.markdown(f"**Sample data for `{agent_name}`:**")
        st.json(_SAMPLE_DATA.get(agent_name, {}))
