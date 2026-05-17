"""
Scenario 5 — Interviewer Feedback

User question: "How is each interviewer performing and how is scheduling holding up?"

Agents forced:
  resource_optimization — workload per interviewer, overload flags, avg ratings
  evaluation            — verifies the workload analysis output quality
  optimization          — reports token cost and latency for the run

Note: This is a lightweight scenario (3 agents) intended for regular
weekly/monthly scheduling reviews — not a full pipeline diagnostic.

Required data:
  interviewers  — interviewer roster with assignment counts and avg ratings
"""
from orchestration.scenarios.base_scenario import BaseScenario

INTERVIEWER_FEEDBACK = BaseScenario(
    name="interviewer_feedback",
    description="Review interviewer workload, ratings, and scheduling health",
    default_query=(
        "Review each interviewer's current assignment load, average rating, and scheduling "
        "patterns. Flag anyone who is over-capacity or showing signs of rating inconsistency, "
        "and recommend concrete scheduling adjustments."
    ),
    forced_agents=["resource_optimization", "evaluation", "optimization"],
    required_data_keys=["interviewers"],
)
