"""
Coordinator Agent — top-level orchestrator using LangGraph.

Pipeline graph (StateGraph):
  route → run_insights → run_support → END

  route:        RoutingAgent selects which insight agents to call.
  run_insights: Selected insight agents run in parallel (asyncio.gather).
  run_support:  EvaluationAgent + OptimizationAgent run after insights,
                receiving previous insight outputs in AgentContext.

The compiled graph is cached as a class variable so it is built once
per process, not once per request.

Agent registry:
  Call CoordinatorAgent.register(AgentClass) to add an agent.
  _load_available_agents() tries all Day 8-10 agents at startup and
  silently skips any whose modules are not yet installed.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, ClassVar, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from agents.base.base_agent import AgentContext, BaseAgent
from agents.coordinator.response_assembler import CoordinatorResponse, assemble_response
from agents.routing.agent_selector import SUPPORT_AGENTS, default_agents
from agents.routing.routing_agent import RoutingAgent
from shared.contracts.agent_output import AgentOutput

logger = logging.getLogger(__name__)

# ── Module-level agent registry ─────────────────────────────────────────────────
# Defined outside the class so LangGraph node functions can access it without
# a circular import (nodes are module-level, not class methods).

_AGENT_REGISTRY: dict[str, type[BaseAgent]] = {}


# ── LangGraph state schema ───────────────────────────────────────────────────────

class PipelineState(TypedDict):
    """Shared mutable state threaded through all LangGraph nodes."""

    query: str
    run_id: str
    structured_data: dict[str, Any]
    rag_collections: list[str]
    filters: dict[str, Any]
    pipeline_start: float
    forced_agents: list[str]       # non-empty → skip RoutingAgent LLM call
    routing_output: AgentOutput | None
    selected_agents: list[str]
    insight_outputs: list[AgentOutput]
    support_outputs: list[AgentOutput]


# ── Pipeline request ─────────────────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    """Input to run_pipeline() — submitted by FastAPI / Streamlit."""

    query: str
    structured_data: dict = {}
    rag_collections: list[str] = []
    filters: dict = {}
    run_id: str = ""
    forced_agents: list[str] = []  # scenario-set list bypasses routing LLM


# ── Coordinator Agent ────────────────────────────────────────────────────────────

class CoordinatorAgent(BaseAgent):
    """Orchestrates the full multi-agent hiring analysis pipeline via LangGraph."""

    agent_name = "coordinator"
    model_tier  = "coordinator"

    _graph: ClassVar[Any] = None  # compiled LangGraph StateGraph — built once

    def __init__(self) -> None:
        super().__init__()
        _load_available_agents()
        if CoordinatorAgent._graph is None:
            CoordinatorAgent._graph = _build_pipeline_graph()

    # ── Class-level registry ────────────────────────────────────────────────────

    @classmethod
    def register(cls, agent_class: type[BaseAgent]) -> None:
        """Register an agent class so the pipeline can instantiate it by name."""
        _AGENT_REGISTRY[agent_class.agent_name] = agent_class
        logger.debug("Registered agent: %s", agent_class.agent_name)

    # ── Primary public entry point ──────────────────────────────────────────────

    async def run_pipeline(self, request: PipelineRequest) -> CoordinatorResponse:
        """Execute the full ATS pipeline via the LangGraph state machine.

        The graph drives:  route → run_insights → run_support → assemble.

        Args:
            request: PipelineRequest with query, optional structured data / filters.

        Returns:
            CoordinatorResponse with aggregated insights, recommendations, summary.
        """
        run_id = request.run_id or str(uuid.uuid4())[:8]
        logger.info("[%s] Pipeline started — query: %.80s", run_id, request.query)

        initial_state: PipelineState = {
            "query":            request.query,
            "run_id":           run_id,
            "structured_data":  request.structured_data,
            "rag_collections":  request.rag_collections,
            "filters":          request.filters,
            "pipeline_start":   time.monotonic(),
            "forced_agents":    list(request.forced_agents),
            "routing_output":   None,
            "selected_agents":  [],
            "insight_outputs":  [],
            "support_outputs":  [],
        }

        final_state: PipelineState = await CoordinatorAgent._graph.ainvoke(initial_state)

        all_outputs: list[AgentOutput] = []
        if final_state.get("routing_output"):
            all_outputs.append(final_state["routing_output"])
        all_outputs.extend(final_state.get("insight_outputs", []))
        all_outputs.extend(final_state.get("support_outputs", []))

        return assemble_response(
            run_id=run_id,
            query=request.query,
            outputs=all_outputs,
            pipeline_start=final_state["pipeline_start"],
        )

    # ── BaseAgent ABC requirement ───────────────────────────────────────────────

    async def analyse(self, context: AgentContext) -> AgentOutput:
        """Not invoked directly — use run_pipeline() instead."""
        return AgentOutput.skipped(agent_name=self.agent_name)


# ── LangGraph node functions ─────────────────────────────────────────────────────

async def _route_node(state: PipelineState) -> dict:
    """Node 1 — select agents via scenario forced list OR RoutingAgent LLM call."""
    forced = state.get("forced_agents") or []
    if forced:
        # Scenario pre-selected agents — skip LLM routing entirely
        logger.info("[%s] Forced agents (scenario): %s", state["run_id"], forced)
        routing_output = AgentOutput.skipped(agent_name="routing")
        routing_output.metadata["selected_agents"] = forced
        routing_output.metadata["routing_mode"] = "forced"
        return {"routing_output": routing_output, "selected_agents": forced}

    context = _build_context(state)
    output = await RoutingAgent().run(context)
    selected = output.metadata.get("selected_agents") or default_agents()
    logger.info("[%s] Routing selected: %s", state["run_id"], selected)
    return {"routing_output": output, "selected_agents": selected}


async def _run_insights_node(state: PipelineState) -> dict:
    """Node 2 — run selected insight agents in parallel."""
    insight_names = [a for a in state["selected_agents"] if a not in SUPPORT_AGENTS]
    context = _build_context(state)
    outputs = await _run_parallel(insight_names, context)
    return {"insight_outputs": outputs}


async def _run_support_node(state: PipelineState) -> dict:
    """Node 3 — run Evaluation + Optimization with insight outputs in context."""
    support_names = [a for a in state["selected_agents"] if a in SUPPORT_AGENTS]
    context = AgentContext(
        query=state["query"],
        run_id=state["run_id"],
        structured_data=state["structured_data"],
        rag_collections=state["rag_collections"],
        filters=state["filters"],
        previous_outputs=state.get("insight_outputs", []),
    )
    outputs = await _run_parallel(support_names, context)
    return {"support_outputs": outputs}


# ── Shared helpers ───────────────────────────────────────────────────────────────

def _build_context(state: PipelineState) -> AgentContext:
    return AgentContext(
        query=state["query"],
        run_id=state["run_id"],
        structured_data=state["structured_data"],
        rag_collections=state["rag_collections"],
        filters=state["filters"],
    )


async def _run_parallel(
    agent_names: list[str],
    context: AgentContext,
) -> list[AgentOutput]:
    """Instantiate and run a list of agents concurrently via asyncio.gather."""

    async def _one(name: str) -> AgentOutput:
        cls = _AGENT_REGISTRY.get(name)
        if cls is None:
            logger.warning("Agent '%s' not in registry — skipping.", name)
            return AgentOutput.skipped(agent_name=name)
        try:
            return await cls().run(context)
        except Exception as exc:
            logger.error("Agent '%s' raised: %s", name, exc)
            return AgentOutput.error(agent_name=name, reason=str(exc))

    return list(await asyncio.gather(*[_one(n) for n in agent_names]))


def _build_pipeline_graph() -> Any:
    """Build and compile the LangGraph StateGraph for the ATS pipeline."""
    graph: StateGraph = StateGraph(PipelineState)

    graph.add_node("route",        _route_node)
    graph.add_node("run_insights", _run_insights_node)
    graph.add_node("run_support",  _run_support_node)

    graph.add_edge(START,          "route")
    graph.add_edge("route",        "run_insights")
    graph.add_edge("run_insights", "run_support")
    graph.add_edge("run_support",  END)

    return graph.compile()


# ── Auto-register agents as they become available ───────────────────────────────

def _load_available_agents() -> None:
    """Try to import and register each specialist agent.

    Uses try/except so the Coordinator works during gradual day-by-day
    implementation — agents not yet built are silently skipped.
    """
    candidates = [
        ("agents.insight.pipeline_health.pipeline_health_agent",         "PipelineHealthAgent"),
        ("agents.insight.sourcing_quality.sourcing_quality_agent",       "SourcingQualityAgent"),
        ("agents.insight.improvement_action.improvement_action_agent",   "ImprovementActionAgent"),
        ("agents.insight.resource_optimization.resource_optimization_agent", "ResourceOptimizationAgent"),
        ("agents.insight.offer_insights.offer_insights_agent",           "OfferInsightsAgent"),
        ("agents.support.evaluation.evaluation_agent",                   "EvaluationAgent"),
        ("agents.support.optimization.optimization_agent",               "OptimizationAgent"),
    ]
    import importlib
    for module_path, class_name in candidates:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            CoordinatorAgent.register(cls)
        except ImportError:
            pass  # agent not yet built — registered when its Day arrives
        except Exception as exc:
            logger.warning("Could not register %s: %s", class_name, exc)
