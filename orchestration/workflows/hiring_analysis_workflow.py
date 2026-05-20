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

from agents.base import langfuse_helper
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

        # Create a named top-level Langfuse trace for this pipeline run
        trace = langfuse_helper.create_trace(
            run_id=run_id,
            query=query,
            metadata={"scenario": request.scenario or "free_form", "filters": request.filters},
        )

        # Fetch live structured data from PostgreSQL so agents have real metrics
        structured_data = await self._fetch_structured_data(request.filters)
        logger.info(
            "[%s] Structured data loaded — stages=%d candidates=%d rejections=%d "
            "interviewers=%d offers=%d",
            run_id,
            len(structured_data.get("stages", [])),
            len(structured_data.get("candidates", [])),
            len(structured_data.get("rejections", [])),
            len(structured_data.get("interviewers", [])),
            len(structured_data.get("offers", [])),
        )

        pipeline_req = PipelineRequest(
            query=query,
            structured_data=structured_data,
            rag_collections=[],
            filters=request.filters,
            run_id=run_id,
            forced_agents=forced_agents,
            langfuse_trace=trace,
        )
        response = await self._coordinator.run_pipeline(pipeline_req)
        _update_run_state(run_state, response)

        langfuse_helper.update_trace(trace, {
            "status": response.status,
            "agents_run": [o.agent_name for o in response.agent_outputs if o.status != "skipped"],
            "total_tokens": response.total_tokens,
            "total_latency_ms": response.total_latency_ms,
        })
        langfuse_helper.flush()

        try:
            from orchestration.state import run_history_store
            run_history_store.append_run(response, scenario=request.scenario)
        except Exception as exc:
            logger.warning("[%s] Could not save run to history store: %s", run_id, exc)

        return response

    async def _fetch_structured_data(self, filters: dict) -> dict[str, Any]:
        """Fetch all hiring data from PostgreSQL and shape it for agent consumption.

        Agents compute structured metrics from this data — empty structured_data
        causes every metric calculator to return data_quality='missing', leading
        to LLM hallucination and low confidence scores.
        """
        try:
            from database.sessions.async_session import AsyncSessionLocal
            from sqlalchemy import text

            position_list = filters.get("position") or []
            channel_list  = filters.get("source_channel") or []

            # Candidate filter conditions shared across JOIN queries
            cond_parts = ["1=1"]
            params: dict[str, Any] = {}
            if position_list:
                cond_parts.append("c.position = ANY(:positions)")
                params["positions"] = position_list
            if channel_list:
                cond_parts.append("c.source_channel = ANY(:channels)")
                params["channels"] = channel_list
            cand_where = " AND ".join(cond_parts)

            async with AsyncSessionLocal() as session:

                # 1. Stage funnel — PipelineHealthAgent needs entered/exited/avg_days
                r = await session.execute(text(f"""
                    SELECT s.stage_name,
                           COUNT(*)                                              AS candidates_entered,
                           COUNT(CASE WHEN s.outcome IN ('passed','accepted') THEN 1 END)
                                                                                AS candidates_exited,
                           COALESCE(AVG(s.duration_hours) / 24.0, 0)           AS avg_days_in_stage
                    FROM ats.interview_stages s
                    JOIN ats.candidates c ON c.id = s.candidate_id
                    WHERE {cand_where}
                    GROUP BY s.stage_name
                    ORDER BY CASE s.stage_name
                        WHEN 'application_review'  THEN 1
                        WHEN 'phone_screen'         THEN 2
                        WHEN 'technical_assessment' THEN 3
                        WHEN 'panel_interview'      THEN 4
                        WHEN 'final_interview'      THEN 5
                        WHEN 'offer'                THEN 6
                        ELSE 7 END
                """), params)
                stages = [dict(row._mapping) for row in r]

                # 2. Candidates — SourcingQualityAgent + stuck-candidate detection
                #    quality_score: normalize experience_years to 0-1 by position's typical ceiling
                r = await session.execute(text(f"""
                    SELECT c.id::text                                           AS candidate_id,
                           c.source_channel,
                           CASE c.overall_status
                               WHEN 'withdrew' THEN 'withdrawn'
                               ELSE c.overall_status
                           END                                                  AS status,
                           c.current_stage                                      AS stage,
                           c.experience_years,
                           ROUND(LEAST(
                               c.experience_years / CASE c.position
                                   WHEN 'Software Engineer'        THEN 5.0
                                   WHEN 'Senior Software Engineer' THEN 12.0
                                   WHEN 'Data Scientist'           THEN 8.0
                                   WHEN 'Product Manager'          THEN 10.0
                                   WHEN 'DevOps Engineer'          THEN 8.0
                                   ELSE 8.0 END,
                               1.0
                           )::numeric, 2)                                       AS quality_score,
                           COALESCE(
                               EXTRACT(EPOCH FROM (NOW() - MAX(s.entered_at))) / 86400.0,
                               0
                           )                                                    AS days_in_current_stage
                    FROM ats.candidates c
                    LEFT JOIN ats.interview_stages s
                        ON s.candidate_id = c.id AND s.stage_name = c.current_stage
                    WHERE {cand_where}
                    GROUP BY c.id, c.source_channel, c.overall_status,
                             c.current_stage, c.experience_years, c.position
                """), params)
                candidates = [dict(row._mapping) for row in r]

                # 3. Rejections — ImprovementActionAgent
                r = await session.execute(text(f"""
                    SELECT r.stage_name         AS stage,
                           r.reason_category    AS rejection_category,
                           r.reason_detail      AS reason
                    FROM ats.rejections r
                    JOIN ats.candidates c ON c.id = r.candidate_id
                    WHERE {cand_where}
                """), params)
                rejections = [dict(row._mapping) for row in r]

                # 4. Interviewers with workload — ResourceOptimizationAgent
                #    avg_rating: fraction of completed interviews with outcome='passed'
                r = await session.execute(text("""
                    SELECT i.id::text                                            AS interviewer_id,
                           i.name,
                           i.department,
                           i.role,
                           COUNT(s.id)                                           AS interviews_assigned,
                           ROUND(COALESCE(
                               AVG(CASE WHEN s.outcome = 'passed' THEN 1.0 ELSE 0.0 END),
                               0.0
                           )::numeric, 2)                                        AS avg_rating
                    FROM ats.interviewers i
                    LEFT JOIN ats.interview_stages s ON s.interviewer_id = i.id
                    WHERE i.is_active = true
                    GROUP BY i.id, i.name, i.department, i.role
                    ORDER BY COUNT(s.id) DESC
                """))
                interviewers = [dict(row._mapping) for row in r]

                # 5. Offers — OfferInsightsAgent
                r = await session.execute(text(f"""
                    SELECT o.position,
                           o.status,
                           o.rejection_reason                                    AS decline_reason,
                           o.salary_offered,
                           ROUND(COALESCE(
                               EXTRACT(EPOCH FROM (o.responded_at - o.offered_at)) / 86400.0,
                               NULL
                           )::numeric, 1)                                        AS days_to_respond
                    FROM ats.offers o
                    JOIN ats.candidates c ON c.id = o.candidate_id
                    WHERE {cand_where}
                """), params)
                offers = [dict(row._mapping) for row in r]

            return {
                "stages":       stages,
                "candidates":   candidates,
                "rejections":   rejections,
                "interviewers": interviewers,
                "offers":       offers,
            }

        except Exception as exc:
            logger.warning("Could not fetch structured data from PostgreSQL: %s", exc)
            return {}

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
