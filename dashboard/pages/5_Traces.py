"""
Page 5 — Traces: Langfuse LLM Observability

One entry per user prompt (= one Langfuse trace per pipeline run).
Each trace expands to show a hierarchical step tree:
  LangGraph node span
    └─ RAG retrieval span(s)
    └─ LLM generation(s)

User feedback (👍/👎) is submitted as a Langfuse score on the top-level trace.
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

import base64
import httpx
import streamlit as st
from configs.settings import settings

st.set_page_config(page_title="Traces | ATS Insights", layout="wide", page_icon="🔭")
st.title("🔭 LLM Traces")
st.caption("One entry per analysis run — expand to drill into each agent step.")

# ── Guard ─────────────────────────────────────────────────────────────────────

if not settings.langfuse.enabled:
    st.warning(
        "Langfuse is disabled. Set `LANGFUSE_ENABLED=true` and add "
        "`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` in `.env`, then restart."
    )
    st.stop()

# ── Auth helper ───────────────────────────────────────────────────────────────

def _auth_header() -> str:
    token = base64.b64encode(
        f"{settings.langfuse.public_key}:{settings.langfuse.secret_key}".encode()
    ).decode()
    return f"Basic {token}"


# ── Langfuse API helpers ───────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner="Fetching traces from Langfuse…")
def fetch_traces(limit: int, name_filter: str) -> list[dict]:
    params: dict = {"limit": limit, "page": 1}
    if name_filter:
        params["name"] = name_filter
    url = f"{settings.langfuse.host.rstrip('/')}/api/public/traces"
    resp = httpx.get(url, headers={"Authorization": _auth_header()}, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


@st.cache_data(ttl=60, show_spinner=False)
def fetch_trace_detail(trace_id: str) -> dict:
    url = f"{settings.langfuse.host.rstrip('/')}/api/public/traces/{trace_id}"
    resp = httpx.get(url, headers={"Authorization": _auth_header()}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def submit_score(trace_id: str, value: float, comment: str = "") -> bool:
    url = f"{settings.langfuse.host.rstrip('/')}/api/public/scores"
    payload: dict = {
        "traceId": trace_id,
        "name": "user_feedback",
        "value": value,
        "dataType": "NUMERIC",
    }
    if comment.strip():
        payload["comment"] = comment.strip()
    try:
        resp = httpx.post(
            url, headers={"Authorization": _auth_header()}, json=payload, timeout=10
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        st.error(f"Score submission failed: {exc}")
        return False


# ── Tree builder ──────────────────────────────────────────────────────────────

def _build_obs_tree(observations: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Return (root_observations, children_map) from a flat observations list.

    root_observations — observations with no parentObservationId (directly under trace)
    children_map      — {parent_id: [child_obs, ...]}
    """
    children: dict[str, list[dict]] = {}
    roots: list[dict] = []
    for obs in observations:
        parent_id = obs.get("parentObservationId")
        if parent_id:
            children.setdefault(parent_id, []).append(obs)
        else:
            roots.append(obs)
    # Sort by start time within each level
    roots.sort(key=lambda o: o.get("startTime") or "")
    for kids in children.values():
        kids.sort(key=lambda o: o.get("startTime") or "")
    return roots, children


# ── Step renderer (recursive) ─────────────────────────────────────────────────

_TYPE_ICON = {"SPAN": "◈", "GENERATION": "⚡", "EVENT": "•"}
_TYPE_COLOR = {"SPAN": "#4a90d9", "GENERATION": "#e67e22", "EVENT": "#888"}


def _latency_str(obs: dict) -> str:
    ms = obs.get("latency")
    if ms is None:
        return "—"
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.0f} ms"


def _token_str(obs: dict) -> str:
    usage = obs.get("usage") or {}
    inp = usage.get("input")
    out = usage.get("output")
    if inp is None and out is None:
        return ""
    return f"{inp or 0} in / {out or 0} out tokens"


def _render_obs_node(obs: dict, children: dict[str, list[dict]], depth: int = 0) -> None:
    """Render one observation as an expander; recurse into children."""
    obs_id   = obs.get("id", "")
    obs_name = obs.get("name") or "unnamed"
    obs_type = obs.get("type", "SPAN")
    icon     = _TYPE_ICON.get(obs_type, "•")
    lat      = _latency_str(obs)
    tokens   = _token_str(obs)
    model    = obs.get("model") or ""

    # Build expander label
    label_parts = [f"{icon} **{obs_name}**", f"⏱ {lat}"]
    if tokens:
        label_parts.append(f"🔤 {tokens}")
    if model:
        label_parts.append(f"🤖 {model}")
    label = " &nbsp;·&nbsp; ".join(label_parts)

    kids = children.get(obs_id, [])

    with st.expander(label, expanded=False):
        # Type badge
        st.markdown(
            f'<span style="background:{_TYPE_COLOR.get(obs_type,"#888")};'
            f'color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;">'
            f'{obs_type}</span>',
            unsafe_allow_html=True,
        )

        # Input / output for this step
        obs_input  = obs.get("input")
        obs_output = obs.get("output")
        if obs_input or obs_output:
            in_col, out_col = st.columns(2)
            with in_col:
                if obs_input:
                    st.markdown("**Input**")
                    st.json(obs_input, expanded=False)
            with out_col:
                if obs_output:
                    st.markdown("**Output**")
                    st.json(obs_output, expanded=False)

        # Metadata / status
        status_msg = obs.get("statusMessage")
        if status_msg:
            st.caption(f"Status: {status_msg}")

        # Recurse into children
        if kids:
            st.markdown(f"**Sub-steps ({len(kids)})**")
            for child in kids:
                _render_obs_node(child, children, depth + 1)
        elif not obs_input and not obs_output:
            st.caption("No detail recorded for this step.")


# ── Controls ──────────────────────────────────────────────────────────────────

col_limit, col_name, col_refresh = st.columns([1, 2, 1])
with col_limit:
    limit = st.selectbox("Show last N runs", [10, 25, 50, 100], index=0)
with col_name:
    name_filter = st.text_input(
        "Filter by trace name", placeholder="e.g. run_ (leave blank for all)"
    )
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Fetch ─────────────────────────────────────────────────────────────────────

try:
    traces = fetch_traces(limit, name_filter.strip())
except httpx.HTTPStatusError as exc:
    st.error(f"Langfuse API error {exc.response.status_code}: {exc.response.text[:300]}")
    st.stop()
except Exception as exc:
    st.error(f"Could not reach Langfuse: {exc}")
    st.stop()

if not traces:
    st.info("No traces yet. Run a query on the **Analysis** page to generate some.")
    st.stop()

st.markdown(f"**{len(traces)} run(s)** — one entry per analysis prompt. Expand to drill into steps.")
st.markdown("---")

# ── One entry per trace (= one per user prompt) ───────────────────────────────

for trace in traces:
    trace_id   = trace.get("id", "")
    trace_name = trace.get("name") or "unnamed"
    ts         = (trace.get("timestamp") or "")[:19].replace("T", " ")
    latency_ms = trace.get("latency")
    latency_str = f"{latency_ms / 1000:.2f} s" if latency_ms else "—"
    total_cost  = trace.get("totalCost")
    cost_str    = f"${total_cost:.5f}" if total_cost else ""

    # Pull scenario and query from trace metadata if available
    meta       = trace.get("metadata") or {}
    scenario   = meta.get("scenario") or "—"
    lf_url     = f"{settings.langfuse.host.rstrip('/')}/trace/{trace_id}"

    # Top-level expander: one per run
    header_parts = [f"**{trace_name}**", ts, f"⏱ {latency_str}"]
    if cost_str:
        header_parts.append(f"💰 {cost_str}")
    if scenario and scenario != "—":
        header_parts.append(f"📋 {scenario}")
    header = " &nbsp;·&nbsp; ".join(header_parts)

    with st.expander(header, expanded=False):

        # ── Run summary row ────────────────────────────────────────────────────
        sum_cols = st.columns([3, 1, 1, 1])
        with sum_cols[0]:
            query_text = trace.get("input") or meta.get("query") or "—"
            if isinstance(query_text, dict):
                query_text = query_text.get("query") or str(query_text)
            st.markdown(f"**Query:** {str(query_text)[:200]}")
        with sum_cols[1]:
            st.metric("Latency", latency_str)
        with sum_cols[2]:
            st.metric("Cost", cost_str or "—")
        with sum_cols[3]:
            st.markdown(f"[Open in Langfuse ↗]({lf_url})")

        st.markdown("---")

        # ── Fetch full trace detail (includes observations) ────────────────────
        try:
            detail = fetch_trace_detail(trace_id)
        except Exception as exc:
            st.warning(f"Could not load step detail: {exc}")
            detail = trace

        observations = detail.get("observations") or []

        if observations:
            roots, children_map = _build_obs_tree(observations)

            # Summary counts
            n_spans = sum(1 for o in observations if o.get("type") == "SPAN")
            n_gens  = sum(1 for o in observations if o.get("type") == "GENERATION")
            st.markdown(
                f"**Pipeline Steps** &nbsp;·&nbsp; "
                f"◈ {n_spans} spans &nbsp;·&nbsp; ⚡ {n_gens} LLM generations"
            )

            # Render root-level nodes (LangGraph nodes: route, run_insights, run_support)
            for root_obs in roots:
                _render_obs_node(root_obs, children_map, depth=0)
        else:
            st.caption("No step detail recorded for this run.")

        # ── User feedback ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Rate this run**")
        feedback_key = f"feedback_submitted_{trace_id}"
        if st.session_state.get(feedback_key):
            st.success("Feedback recorded — thank you!")
        else:
            comment = st.text_input(
                "Optional comment",
                key=f"comment_{trace_id}",
                placeholder="What was helpful or missing?",
                label_visibility="collapsed",
            )
            fb_col1, fb_col2, _ = st.columns([1, 1, 6])
            with fb_col1:
                if st.button("👍 Good", key=f"thumbs_up_{trace_id}"):
                    if submit_score(trace_id, 1.0, comment):
                        st.session_state[feedback_key] = True
                        st.rerun()
            with fb_col2:
                if st.button("👎 Poor", key=f"thumbs_down_{trace_id}"):
                    if submit_score(trace_id, 0.0, comment):
                        st.session_state[feedback_key] = True
                        st.rerun()

    st.markdown("")  # breathing room between runs
