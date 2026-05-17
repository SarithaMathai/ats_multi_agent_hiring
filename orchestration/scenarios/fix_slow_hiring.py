"""
Scenario 1 — Fix Slow Hiring

User question: "Why is hiring taking so long and what should we do about it?"

Agents forced:
  pipeline_health     — diagnoses which stages are slow and where candidates stall
  improvement_action  — retrieves MCP case studies and best practices to fix those stages
  evaluation          — verifies quality of both outputs
  optimization        — reports token cost and latency for the run

Required data:
  stages      — stage-level conversion rates and average days
  candidates  — individual candidate status for stuck-candidate detection
  rejections  — rejection records for improvement_action root-cause analysis
"""
from orchestration.scenarios.base_scenario import BaseScenario

FIX_SLOW_HIRING = BaseScenario(
    name="fix_slow_hiring",
    description="Identify bottlenecks and get corrective action recommendations",
    default_query=(
        "Where is the hiring process slowest? Identify stages with the highest drop-off "
        "and longest time-in-stage, then recommend specific corrective actions to speed up hiring."
    ),
    forced_agents=["pipeline_health", "improvement_action", "evaluation", "optimization"],
    required_data_keys=["stages", "candidates", "rejections"],
)
