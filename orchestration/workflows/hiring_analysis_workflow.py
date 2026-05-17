"""
HiringAnalysisWorkflow — the single entry point for all ATS analyses.

Responsibilities:
  1. Translate a CoordinatorRequest (or named scenario + filters) into a
     PipelineRequest understood by CoordinatorAgent.
  2. When a named scenario is used, inject forced_agents so the LangGraph
     pipeline skips the RoutingAgent LLM call and runs deterministically.
  3. Wrap the CoordinatorResponse in a RunState for audit / dashboard use.
  4. Expose scenario_names() so FastAPI and Streamlit can populate dropdowns.

Usage:
    wf = HiringAnalysisWorkflow()

    # Free-form query (RoutingAgent decides which agents to call)
    response = await wf.run(CoordinatorRequest(query="Why is hiring slow?"))

    # Named scenario (deterministic agent selection, no routing LLM call)
    response = await wf.run_scenario(
        name="fix_slow_hiring",
        filters={"department": "Engineering"},
        structured_data={"stages": [...], "candidates": [...], "rejections": [...]},
    )
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from agents.coordinator.coordinator_agent import CoordinatorAgent, PipelineRequest
from agents.coordinator.response_assembler import CoordinatorResponse
from orchestration.scenarios.balance_workload import BALANCE_WORKLOAD
from orchestration.scenarios.base_scenario import BaseScenario
from orchestration.scenarios.executive_metrics import EXECUTIVE_METRICS
from orchestration.scenarios.fix_slow_hiring import FIX_SLOW_HIRING
from orchestration.scenarios.interviewer_feedback import INTERVIEWER_FEEDBACK
from orchestration.scenarios.investigate_rejections import INVESTIGATE_REJECTIONS
from orchestration.state.run_state import RunState
from orchestration.workflows.base_workflow import BaseWorkflow
from shared.contracts.coordinator_request import CoordinatorRequest

logger = logging.getLogger(__name__)

# ── Scenario registry ────────────────────────────────────────────────────────────

_SCENARIOS: dict[str, BaseScenario] = {
    s.name: s for s in [
        FIX_SLOW_HIRING,
        BALANCE_WORKLOAD,
        INVESTIGATE_REJECTIONS,
        EXECUTIVE_METRICS,
        INTERVIEWER_FEEDBACK,
    ]
}


# ── Workflow ─────────────────────────────────────────────────────────────────────

class HiringAnalysisWorkflow(BaseWorkflow):
    """Facade over CoordinatorAgent that adds scenario management and run tracking."""

    def __init__(self) -> None:
        self._coordinator = CoordinatorAgent()

    # ── Public API ───────────────────────────────────────────────────────────────

    async def run(self, request: CoordinatorRequest) -> CoordinatorResponse:
        """Execute a free-form or scenario-tagged CoordinatorRequest.

        If request.scenario matches a registered scenario the forced_agents list
        is injected automatically — no RoutingAgent LLM call is made.
        Otherwise the RoutingAgent decides which agents to invoke.

        Args:
            request: CoordinatorRequest from FastAPI or Streamlit.

        Returns:
            CoordinatorResponse with aggregated insights, recommendations, summary.
        """
        scenario = _SCENARIOS.get(request.scenario or "")
        forced_agents = scenario.forced_agents if scenario else []
        query = scenario.build_query(request.query) if scenario else request.query

        run_id = str(uuid.uuid4())[:8]
        run_state = RunState(
            run_id=run_id,
            scenario_name=request.scenario,
            query=query,
            forced_agents=forced_agents,
        )
        logger.info("[%s] Workflow.run — scenario=%s", run_id, request.scenario)

        pipeline_req = PipelineRequest(
            query=query,
            structured_data={},
            rag_collections=[],
            filters=request.filters,
            run_id=run_id,
            forced_agents=forced_agents,
        )
        response = await self._coordinator.run_pipeline(pipeline_req)
        _update_run_state(run_state, response)
        return response

    async def run_scenario(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        structured_data: dict[str, Any] | None = None,
        query_override: str | None = None,
    ) -> CoordinatorResponse:
        """Execute a named scenario with caller-supplied data.

        Args:
            name:            Scenario identifier (see scenario_names()).
            filters:         Optional dict of filters forwarded to all agents.
            structured_data: Pre-loaded DB records for the insight agents.
            query_override:  If set, overrides the scenario's default_query.

        Returns:
            CoordinatorResponse with aggregated insights and recommendations.

        Raises:
            ValueError: if name is not a registered scenario.
        """
        scenario = _SCENARIOS.get(name)
        if scenario is None:
            raise ValueError(
                f"Unknown scenario '{name}'. "
                f"Available: {sorted(_SCENARIOS)}"
            )

        filters = filters or {}
        structured_data = structured_data or {}
        query = scenario.build_query(query_override)
        run_id = str(uuid.uuid4())[:8]

        # Warn about missing data keys — agents degrade gracefully but results improve
        # when all expected keys are present.
        missing = scenario.missing_data_keys(structured_data)
        if missing:
            logger.warning(
                "[%s] Scenario '%s' missing data keys: %s — agents will degrade gracefully",
                run_id, name, missing,
            )

        run_state = RunState(
            run_id=run_id,
            scenario_name=name,
            query=query,
            forced_agents=scenario.forced_agents,
        )
        logger.info("[%s] Workflow.run_scenario — %s, agents=%s", run_id, name, scenario.forced_agents)

        pipeline_req = PipelineRequest(
            query=query,
            structured_data=structured_data,
            rag_collections=[],
            filters=filters,
            run_id=run_id,
            forced_agents=scenario.forced_agents,
        )
        response = await self._coordinator.run_pipeline(pipeline_req)
        _update_run_state(run_state, response)
        return response

    def scenario_names(self) -> list[str]:
        """Return sorted list of all registered scenario identifiers."""
        return sorted(_SCENARIOS)

    def scenario_info(self) -> list[dict[str, Any]]:
        """Return metadata for all scenarios (for Streamlit dropdowns / API docs)."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "agents": s.forced_agents,
                "required_data": s.required_data_keys,
            }
            for s in _SCENARIOS.values()
        ]

    def get_scenario(self, name: str) -> BaseScenario:
        """Return the scenario object for inspection. Raises ValueError if unknown."""
        if name not in _SCENARIOS:
            raise ValueError(f"Unknown scenario '{name}'.")
        return _SCENARIOS[name]


# ── Private helpers ──────────────────────────────────────────────────────────────

def _update_run_state(run_state: RunState, response: CoordinatorResponse) -> None:
    agents_run = [o.agent_name for o in response.agent_outputs if o.status != "skipped"]
    run_state.mark_complete(
        status=response.status,
        agents_run=agents_run,
        total_tokens=response.total_tokens,
        total_latency_ms=response.total_latency_ms,
    )
    logger.info(
        "[%s] Run complete — status=%s, agents=%s, tokens=%d, latency=%.0f ms",
        run_state.run_id,
        run_state.status,
        agents_run,
        run_state.total_tokens,
        run_state.total_latency_ms,
    )
