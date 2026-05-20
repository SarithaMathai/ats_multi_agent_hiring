"""
Centralised Langfuse tracing utilities used by every layer of the pipeline.

Design goals:
  - Every function is a no-op when Langfuse is disabled or not installed.
  - No function ever raises — all exceptions are swallowed so tracing failures
    cannot break pipeline execution.
  - Thin wrappers over the Langfuse v4 SDK so callers never import langfuse directly.

Hierarchy produced inside Langfuse for one user query:

  Trace: ats_pipeline  (run_id, query, scenario)
    ├── Span: route                      (LangGraph node)
    │     └── Generation: routing_llm
    ├── Span: run_insights_parallel      (LangGraph node)
    │     ├── Span: rag:ats_feedback     (ChromaDB retrieval)
    │     │     └── Generation: pipeline_health_llm
    │     └── Span: rag:ats_resumes      (ChromaDB retrieval)
    │           └── Generation: sourcing_quality_llm
    └── Span: run_support_sequential     (LangGraph node)
          ├── Generation: evaluation_llm
          └── Generation: optimization_llm
"""
from __future__ import annotations

import logging
from typing import Any

from configs.settings import settings

logger = logging.getLogger(__name__)


# ── Internal client singleton ───────────────────────────────────────────────────

_client: Any = None   # Langfuse() instance, created once


def _get_client() -> Any:
    """Return the shared Langfuse client, or None if disabled / unavailable."""
    global _client
    if _client is not None:
        return _client
    if not settings.langfuse.enabled:
        return None
    try:
        import os
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse.public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse.secret_key
        os.environ["LANGFUSE_HOST"]       = settings.langfuse.host

        from langfuse import Langfuse
        _client = Langfuse()
        _client.auth_check()
        logger.info("Langfuse client initialised (host=%s)", settings.langfuse.host)
        return _client
    except Exception as exc:
        logger.warning("Langfuse client init failed — tracing disabled: %s", exc)
        return None


# ── Public API ──────────────────────────────────────────────────────────────────

def create_trace(
    run_id: str,
    query: str,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Create and return a top-level Langfuse trace for one pipeline run.

    Returns None if Langfuse is disabled or unavailable.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        return client.trace(
            id=run_id,
            name="ats_pipeline",
            input={"query": query},
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.debug("create_trace failed: %s", exc)
        return None


def create_span(
    parent: Any,
    name: str,
    input_data: dict[str, Any] | None = None,
) -> Any:
    """Create a child span on *parent* (a trace or another span).

    Returns None if *parent* is None or span creation fails.
    """
    if parent is None:
        return None
    try:
        return parent.span(name=name, input=input_data or {})
    except Exception as exc:
        logger.debug("create_span(%s) failed: %s", name, exc)
        return None


def end_span(span: Any, output_data: dict[str, Any] | None = None) -> None:
    """End a span and optionally attach output metadata."""
    if span is None:
        return
    try:
        span.end(output=output_data or {})
    except Exception as exc:
        logger.debug("end_span failed: %s", exc)


def update_trace(trace: Any, output_data: dict[str, Any] | None = None) -> None:
    """Attach final output metadata to the top-level trace."""
    if trace is None:
        return
    try:
        trace.update(output=output_data or {})
    except Exception as exc:
        logger.debug("update_trace failed: %s", exc)


def flush(trace: Any = None) -> None:
    """Flush buffered events to Langfuse cloud.

    Passing the trace is optional — the shared client is always flushed.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.debug("flush failed: %s", exc)


def make_callback_handler(trace_id: str | None = None) -> Any:
    """Return a LangChain CallbackHandler wired to *trace_id*.

    When trace_id is provided the LangChain generation is attached to the
    existing trace rather than creating a new standalone trace.
    Returns None if Langfuse is disabled or unavailable.
    """
    if not settings.langfuse.enabled:
        return None
    _get_client()   # ensure env vars are set before constructing handler
    try:
        import os
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse.public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse.secret_key
        os.environ["LANGFUSE_HOST"]       = settings.langfuse.host

        from langfuse.langchain import CallbackHandler
        if trace_id:
            return CallbackHandler(trace_id=trace_id)
        return CallbackHandler()
    except Exception as exc:
        logger.debug("make_callback_handler failed: %s", exc)
        return None


def get_trace_id(trace: Any) -> str | None:
    """Safely extract the trace ID string from a trace object."""
    if trace is None:
        return None
    try:
        return str(trace.id)
    except Exception:
        return None
