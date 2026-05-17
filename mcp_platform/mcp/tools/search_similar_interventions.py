"""
MCP Tool 1 — search_similar_interventions

Semantic search over the ats_interventions ChromaDB collection to find
past case studies that match the described hiring issue.

Design notes:
- Both Embedder and InterventionsCollection are lazy-initialised so importing
  this module never loads PyTorch DLLs or connects to ChromaDB.
- If ChromaDB is unavailable the function returns [] (non-fatal degradation).
- CaseStudy / BestPractice models are defined in vector_store/collections/interventions.py
  and re-exported here so callers have a single import point.
"""
from __future__ import annotations

import logging

from vector_store.collections.interventions import CaseStudy  # re-export

logger = logging.getLogger(__name__)

# Lazy singletons — created only on first call
_embedder = None
_interventions_col = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from rag.embeddings.embedder import Embedder  # lazy — loads PyTorch on first use
        _embedder = Embedder()
    return _embedder


def _get_collection():
    global _interventions_col
    if _interventions_col is None:
        from vector_store.collections.interventions import InterventionsCollection  # lazy — connects ChromaDB
        _interventions_col = InterventionsCollection()
    return _interventions_col


async def search_similar_interventions(
    issue: str,
    role: str | None = None,
    n_results: int = 3,
) -> list[CaseStudy]:
    """Find historical intervention case studies that match the described issue.

    Args:
        issue:     Free-text description of the hiring problem to look up.
        role:      Optional job role filter (e.g. "Software Engineer").
                   When provided, only case studies for that role are returned.
        n_results: Maximum number of case studies to return.

    Returns:
        List of CaseStudy objects ordered by semantic similarity (closest first).
        Returns [] if ChromaDB is unavailable or the collection is empty.
    """
    if not issue or not issue.strip():
        return []
    try:
        embedding = _get_embedder().embed(issue)
        return _get_collection().search_by_issue(
            query_embedding=embedding,
            role=role,
            n_results=n_results,
        )
    except Exception as exc:
        logger.warning("search_similar_interventions failed (ChromaDB unavailable?): %s", exc)
        return []


__all__ = ["search_similar_interventions", "CaseStudy"]
