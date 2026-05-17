"""Dashboard-level constants — keeps all magic strings in one place."""
from __future__ import annotations

API_BASE_URL = "http://localhost:8080"

PAGE_TITLE = "ATS Insights Dashboard"
PAGE_ICON  = "🏢"
LAYOUT     = "wide"

SCENARIOS = [
    "fix_slow_hiring",
    "balance_workload",
    "investigate_rejections",
    "executive_metrics",
    "interviewer_feedback",
]

SCENARIO_LABELS = {
    "fix_slow_hiring":        "Fix Slow Hiring",
    "balance_workload":       "Balance Workload",
    "investigate_rejections": "Investigate Rejections",
    "executive_metrics":      "Executive Metrics (Full Report)",
    "interviewer_feedback":   "Interviewer Feedback",
}

SOURCE_CHANNELS = ["LinkedIn", "Referral", "Indeed", "Agency", "Direct"]
POSITIONS       = ["SWE", "PM", "DS", "Designer", "DevOps"]
DEPARTMENTS     = ["Engineering", "Product", "Design", "Data", "Operations"]

# Confidence colour thresholds
CONF_HIGH   = 0.75
CONF_MEDIUM = 0.50

# Request timeout for httpx calls to FastAPI (seconds)
API_TIMEOUT = 120
