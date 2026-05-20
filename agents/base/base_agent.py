"""
Abstract base class inherited by all 8 ATS agents.

Lifecycle (run() → analyse()):
  run(context)
    ├── calls analyse(context)          ← subclass implements this
    ├── records total latency
    └── traps all exceptions → AgentOutput.error(...)

analyse(context) — typical subclass implementation:
    1. Compute domain metrics from context.structured_data  (pure Python, fast)
    2. Build a domain-specific data_summary string
    3. await self._call_llm(context, data_summary=...)   ← does RAG + LLM + parse
    4. Optionally enrich the returned AgentOutput
    5. return output

AgentContext is defined here so it is available from Day 6 onward.
The orchestration layer (Day 11) imports it from this module.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from agents.base.llm_client import LLMClient
from agents.base.output_parser import parse_llm_output
from agents.base.prompt_builder import build_prompt
from rag.retriever.context_builder import build_context_string
from shared.contracts.agent_output import AgentOutput

if TYPE_CHECKING:
    from rag.retriever.chroma_retriever import ChromaRetriever


# ── Shared context passed into every agent at runtime ───────────────────────────

class AgentContext(BaseModel):
    """Everything an agent needs at runtime — passed in by the Coordinator."""

    query: str
    run_id: str = ""
    structured_data: dict[str, Any] = {}
    rag_collections: list[str] = []          # override per-call; falls back to default_collections
    previous_outputs: list[AgentOutput] = [] # outputs from agents that already ran
    filters: dict[str, Any] = {}
    langfuse_trace: Any = None               # top-level Langfuse trace for this pipeline run

    model_config = {"arbitrary_types_allowed": True}


# ── Base agent ───────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Shared lifecycle for all ATS agents.

    Class-level attributes subclasses MUST set
    ─────────────────────────────────────────────
    agent_name : str
        One of the constants from shared.constants.agent_names.
    model_tier : str
        "coordinator" | "insight" | "support"

    Class-level attributes subclasses MAY override
    ───────────────────────────────────────────────
    default_collections : list[str]
        ChromaDB collections to query when context.rag_collections is empty.
    n_rag_results : int
        How many chunks to retrieve per collection (default 5).
    """

    agent_name: str = "base"
    model_tier: str = "support"
    default_collections: list[str] = []
    n_rag_results: int = 5

    def __init__(self) -> None:
        self._llm = LLMClient(tier=self.model_tier)
        self._retriever: "ChromaRetriever | None" = None  # lazy — loaded on first RAG call

    def _get_retriever(self) -> "ChromaRetriever":
        """Lazy-load the retriever so importing BaseAgent never loads PyTorch DLLs."""
        if self._retriever is None:
            from rag.retriever.chroma_retriever import ChromaRetriever  # lazy import
            self._retriever = ChromaRetriever()
        return self._retriever

    # ── Public entry point ──────────────────────────────────────────────────────

    async def run(self, context: AgentContext) -> AgentOutput:
        """Execute the full agent lifecycle and return a contract-compliant AgentOutput.

        Subclasses never override this — they override analyse() instead.
        """
        start = time.monotonic()
        try:
            output = await self.analyse(context)
            # Overwrite latency with the wall-clock time including any pre-LLM work
            output.latency_ms = (time.monotonic() - start) * 1000
            return output
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            return AgentOutput.error(
                agent_name=self.agent_name,
                reason=str(exc),
                latency_ms=latency_ms,
            )

    # ── Core helper — subclasses call this inside analyse() ─────────────────────

    async def _call_llm(
        self,
        context: AgentContext,
        data_summary: str = "",
        collections: list[str] | None = None,
        n_results: int | None = None,
    ) -> AgentOutput:
        """Retrieve RAG evidence, build the prompt, call the LLM, and parse the output.

        This is the one-liner that insight agents call after computing their metrics:
            output = await self._call_llm(context, data_summary=rich_text)

        Args:
            context:      The runtime context (query, structured_data, filters, …).
            data_summary: Plain-text summary of structured DB data to inject into the prompt.
                          Build this in the subclass using build_data_summary() or custom logic.
            collections:  Override which ChromaDB collections to search.
                          Falls back to context.rag_collections, then default_collections.
            n_results:    Override n_rag_results for this call.

        Returns:
            A fully populated AgentOutput (status="success", evidence from RAG chunks).
        """
        from agents.base import langfuse_helper  # lazy — avoids heavy import at module load

        cols = collections or context.rag_collections or self.default_collections
        k    = n_results if n_results is not None else self.n_rag_results

        chunks = []
        for col in cols:
            rag_span = langfuse_helper.create_span(
                context.langfuse_trace,
                f"rag:{col}",
                {"query": context.query, "collection": col, "n_results": k},
            )
            try:
                new_chunks = self._get_retriever().retrieve(
                    query=context.query,
                    collection_name=col,
                    n_results=k,
                )
                chunks.extend(new_chunks)
                langfuse_helper.end_span(rag_span, {"chunks_retrieved": len(new_chunks)})
            except Exception:
                langfuse_helper.end_span(rag_span, {"error": "retrieval failed"})

        rag_context = build_context_string(chunks, max_tokens=2000)
        system, user = build_prompt(
            agent_name=self.agent_name,
            rag_context=rag_context,
            data_summary=data_summary or self.build_data_summary(context),
            query=context.query,
        )

        trace_id = langfuse_helper.get_trace_id(context.langfuse_trace)
        llm_resp = await self._llm.complete(
            system=system,
            messages=[{"role": "user", "content": user}],
            trace_id=trace_id,
        )

        return parse_llm_output(
            raw=llm_resp.content,
            agent_name=self.agent_name,
            chunks=chunks,
            token_usage=llm_resp.token_usage,
            latency_ms=llm_resp.latency_ms,
        )

    # ── Default helpers subclasses may override ─────────────────────────────────

    def build_data_summary(self, context: AgentContext) -> str:
        """Return a plain-text summary of context.structured_data for the prompt.

        Default: list each key and its record count.
        Subclasses override to produce a richer, domain-specific summary.
        """
        if not context.structured_data:
            return "No structured data available."
        lines = []
        for key, value in context.structured_data.items():
            if isinstance(value, list):
                lines.append(f"{key}: {len(value)} records")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    # ── Abstract method ─────────────────────────────────────────────────────────

    @abstractmethod
    async def analyse(self, context: AgentContext) -> AgentOutput:
        """Domain-specific analysis. Must return a valid AgentOutput.

        Typical implementation pattern:
            async def analyse(self, context: AgentContext) -> AgentOutput:
                # 1. Compute metrics (pure Python, no network calls)
                records = context.structured_data.get("stages", [])
                metrics = compute_my_metrics(records)

                # 2. Build data summary for the prompt
                summary = f"Key metrics:\\n{metrics.to_text()}"

                # 3. Delegate LLM call (handles RAG + prompt + parse)
                return await self._call_llm(context, data_summary=summary)
        """
