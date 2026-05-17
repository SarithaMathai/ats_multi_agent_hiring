"""
Analysis endpoints — run multi-agent hiring analysis over HTTP.

POST /api/v1/analysis/run
    Free-form query, or scenario-tagged via CoordinatorRequest.scenario.
    Payload goes straight to HiringAnalysisWorkflow.run().

POST /api/v1/analysis/scenario/{name}
    Named scenario with caller-supplied filters + structured_data.
    Calls HiringAnalysisWorkflow.run_scenario() — bypasses RoutingAgent LLM.

GET  /api/v1/analysis/scenarios
    List all registered scenario names with metadata.

GET  /api/v1/analysis/runs/{run_id}
    Retrieve a previously cached run result (in-memory store, current process only).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agents.coordinator.response_assembler import CoordinatorResponse
from shared.contracts.coordinator_request import CoordinatorRequest

router = APIRouter(tags=["analysis"])
logger = logging.getLogger(__name__)


# ── In-process run cache (replaced by DB persistence on Day 14) ───────────────

_run_cache: dict[str, CoordinatorResponse] = {}


# ── Request / response models ─────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    """Body for POST /scenario/{name}."""
    filters: dict[str, Any] = Field(default_factory=dict)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    query_override: str | None = None


class ScenarioListItem(BaseModel):
    name: str
    description: str
    agents: list[str]
    required_data: list[str]


# ── Dependency: shared workflow singleton ─────────────────────────────────────

def _get_workflow():
    """FastAPI dependency that returns the app-lifespan workflow singleton."""
    from app.main import get_workflow
    return get_workflow()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/run", response_model=CoordinatorResponse)
async def run_analysis(
    request: CoordinatorRequest,
    workflow=Depends(_get_workflow),
) -> CoordinatorResponse:
    """Run a free-form or scenario-tagged multi-agent analysis."""
    logger.info("POST /run  query=%.80s  scenario=%s", request.query, request.scenario)
    try:
        response = await workflow.run(request)
    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _run_cache[response.run_id] = response
    return response


@router.post("/scenario/{name}", response_model=CoordinatorResponse)
async def run_scenario(
    name: str,
    body: ScenarioRequest,
    workflow=Depends(_get_workflow),
) -> CoordinatorResponse:
    """Run a named scenario (deterministic agent selection, no routing LLM call)."""
    logger.info("POST /scenario/%s  data_keys=%s", name, list(body.structured_data))
    try:
        response = await workflow.run_scenario(
            name=name,
            filters=body.filters,
            structured_data=body.structured_data,
            query_override=body.query_override,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Scenario '%s' error: %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _run_cache[response.run_id] = response
    return response


@router.get("/scenarios", response_model=list[ScenarioListItem])
async def list_scenarios(workflow=Depends(_get_workflow)) -> list[ScenarioListItem]:
    """Return metadata for every registered scenario."""
    return [ScenarioListItem(**item) for item in workflow.scenario_info()]


@router.get("/runs/{run_id}", response_model=CoordinatorResponse)
async def get_run(run_id: str) -> CoordinatorResponse:
    """Retrieve a cached run result by run_id."""
    result = _run_cache.get(run_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found. "
                   "Results are held in-memory per process; restart loses history.",
        )
    return result
