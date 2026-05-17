"""
ATS Insights Dashboard — main Streamlit entry point.

Run with:
    streamlit run dashboard/app.py

Streamlit automatically discovers pages in dashboard/pages/ and renders
them in the sidebar navigation.
"""
import sys
import os

# Make sure the project root (ats_multi_agent_hiring/) is on sys.path
# so imports like `from configs.settings import settings` resolve correctly.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st

from dashboard.api_client import api_client
from dashboard.config import PAGE_ICON, PAGE_TITLE

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar — service status ──────────────────────────────────────────────────

with st.sidebar:
    st.title(f"{PAGE_ICON} ATS Insights")
    st.markdown("---")
    st.subheader("Service Status")

    health = api_client.health_check()
    overall = health.get("status", "error")

    if overall == "ok":
        st.success("All systems operational")
    elif overall == "degraded":
        st.warning("Some services degraded")
    else:
        st.error("Backend offline — start FastAPI server")

    for check in health.get("checks", []):
        icon  = "✅" if check["status"] == "ok" else "❌"
        label = check["service"].capitalize()
        st.caption(f"{icon} {label}: {check.get('detail','')[:40]}")

    st.markdown("---")
    st.caption("ATS Multi-Agent Hiring System v0.1.0")

# ── Home page content (shown when no page is selected) ───────────────────────

st.title("ATS Multi-Agent Hiring System")
st.markdown("""
Welcome to the **ATS Insights Dashboard** — your AI-powered hiring analytics hub.

Use the pages in the **left sidebar** to navigate:

| Page | What you can do |
|---|---|
| **Analysis** | Ask any hiring question in plain English; watch 5 specialised agents respond |
| **Reports** | Explore pre-built visual reports: pipeline funnel, sourcing channels, workload, offers |
| **Agent Tester** | Test any individual agent in isolation (no server required) |
| **Email Stakeholders** | Send a formatted analysis report to HR or leadership by email |

---
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**Start here:** Go to the **Analysis** page and enter a hiring question.")
with col2:
    st.info("**Need charts?** Open **Reports** and upload or paste sample data.")
with col3:
    st.info("**Share results:** Use **Email Stakeholders** to notify your team.")
