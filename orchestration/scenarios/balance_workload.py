"""
Scenario 2 — Balance Workload

User question: "Which interviewers are overloaded and how should we redistribute?"

Agents forced:
  resource_optimization — computes per-interviewer load, flags overloaded panellists
  pipeline_health       — provides pipeline context so workload can be tied to bottlenecks
  evaluation            — verifies quality of both outputs
  optimization          — reports token cost and latency for the run

Required data:
  interviewers  — interviewer roster with assignment counts
  stages        — stage records to correlate workload with pipeline health
"""
from orchestration.scenarios.base_scenario import BaseScenario

BALANCE_WORKLOAD = BaseScenario(
    name="balance_workload",
    description="Identify overloaded interviewers and rebalance scheduling",
    default_query=(
        "Which interviewers are over-capacity and which are underutilised? "
        "Analyse workload distribution and recommend how to rebalance interview "
        "assignments to protect candidate quality and interviewer wellbeing."
    ),
    forced_agents=["resource_optimization", "pipeline_health", "evaluation", "optimization"],
    required_data_keys=["interviewers", "stages"],
)
