"""
Parses the raw JSON text returned by the LLM into a validated AgentOutput.

Contract the LLM is always instructed to return:
  {
    "insights":         ["<finding>", ...],
    "recommendations":  [{"title": "...", "description": "...",
                          "priority": "high|medium|low",
                          "effort":   "low|medium|high"}, ...],
    "confidence_score": <float 0.0–1.0>
  }

Evidence is built from the RAG chunks that were retrieved before the LLM call,
not from the LLM text itself — this keeps citations verifiable.
"""
from __future__ import annotations

import json
import re

from rag.retriever.chroma_retriever import RetrievedChunk
from shared.contracts.agent_output import (
    AgentOutput,
    Evidence,
    Recommendation,
    TokenUsage,
)

_VALID_PRIORITIES = {"high", "medium", "low"}
_VALID_EFFORTS    = {"low", "medium", "high"}


def parse_llm_output(
    raw: str,
    agent_name: str,
    chunks: list[RetrievedChunk],
    token_usage: TokenUsage,
    latency_ms: float,
) -> AgentOutput:
    """Convert raw LLM JSON into a validated AgentOutput.

    Degrades gracefully on malformed JSON: returns status="success" with a
    low confidence score and the raw text as the sole insight so the wider
    pipeline never crashes on a single agent parse failure.
    """
    parsed = _extract_json(raw)

    insights = _extract_list(parsed.get("insights", []))
    recommendations = _extract_recommendations(parsed.get("recommendations", []))
    confidence = _clamp(float(parsed.get("confidence_score", 0.5)))
    evidence = _build_evidence(chunks)

    return AgentOutput(
        agent_name=agent_name,
        status="success",
        insights=insights,
        recommendations=recommendations,
        evidence=evidence,
        confidence_score=confidence,
        token_usage=token_usage,
        latency_ms=latency_ms,
    )


# ── Private helpers ─────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """Best-effort JSON extraction — handles bare JSON, markdown fences, partial blocks."""
    raw = raw.strip()

    # 1. Direct parse (most common when json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Markdown code-fence  ```json { ... } ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. First { ... } block in the text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 4. Fallback — preserve the raw text so nothing is silently lost
    return {
        "insights": [raw[:500]] if raw else ["No output returned by LLM."],
        "recommendations": [],
        "confidence_score": 0.3,
    }


def _extract_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _extract_recommendations(raw_list: object) -> list[Recommendation]:
    if not isinstance(raw_list, list):
        return []
    recs: list[Recommendation] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        priority = item.get("priority", "medium")
        effort   = item.get("effort",   "medium")
        try:
            recs.append(Recommendation(
                title=str(item.get("title", "Recommendation")),
                description=str(item.get("description", "")),
                priority=priority if priority in _VALID_PRIORITIES else "medium",
                effort=effort if effort in _VALID_EFFORTS else "medium",
            ))
        except Exception:
            continue
    return recs


def _build_evidence(chunks: list[RetrievedChunk]) -> list[Evidence]:
    return [
        Evidence(
            source=chunk.collection_name,
            excerpt=chunk.document[:300].strip(),
            relevance_score=_clamp(round(1.0 - chunk.distance, 4)),
            collection=chunk.collection_name,
            document_id=chunk.id,
        )
        for chunk in chunks
    ]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
