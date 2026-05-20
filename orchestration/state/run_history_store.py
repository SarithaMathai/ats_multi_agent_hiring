"""
Persistent run history — thread-safe JSONL file.

One JSON record per line, newest appended at the end.
Survives FastAPI restarts; lives alongside the seed CSV files in data/.

Each record contains:
  - run_id, timestamp, scenario, query, status, summary
  - agents_run, total_tokens, total_latency_ms, total_cost_usd
  - per-agent outputs (insights, recommendations, confidence_score)
  - all_recommendations (deduplicated, priority-sorted)

Reading is always newest-first.  Writing is protected by a threading.Lock
so concurrent FastAPI requests cannot corrupt the file.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.coordinator.response_assembler import CoordinatorResponse

_STORE_PATH = Path(__file__).parent.parent.parent / "data" / "run_history.jsonl"
_lock = threading.Lock()

# gpt-4o-mini blended cost (input + output average)
_COST_PER_TOKEN: float = 0.000_000_375


# ── Write ────────────────────────────────────────────────────────────────────

def append_run(
    response: CoordinatorResponse,
    scenario: str | None = None,
) -> None:
    """Append one completed pipeline run to the JSONL store. Thread-safe."""
    record: dict[str, Any] = {
        "run_id":          response.run_id,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "scenario":        scenario,
        "query":           response.query,
        "status":          response.status,
        "summary":         response.summary,
        "total_tokens":    response.total_tokens,
        "total_latency_ms": round(response.total_latency_ms, 1),
        "total_cost_usd":  round(response.total_tokens * _COST_PER_TOKEN, 6),
        "agents_run": [
            o.agent_name for o in response.agent_outputs
            if o.status != "skipped"
        ],
        "agent_outputs": [
            {
                "agent_name":       o.agent_name,
                "status":           o.status,
                "confidence_score": o.confidence_score,
                "insights":         o.insights,
                "recommendations":  [r.model_dump() for r in o.recommendations],
                "latency_ms":       round(o.latency_ms, 1),
                "metadata":         o.metadata,
            }
            for o in response.agent_outputs
        ],
        "all_recommendations": [r.model_dump() for r in response.all_recommendations],
    }

    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with _STORE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


# ── Read ─────────────────────────────────────────────────────────────────────

def list_runs(
    limit: int = 50,
    scenario: str | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent runs (newest first), optionally filtered by scenario.

    Args:
        limit:    Maximum number of records to return.
        scenario: If set, only return runs whose scenario matches exactly.
                  Pass None to return all scenarios.
    """
    if not _STORE_PATH.exists():
        return []

    records: list[dict] = []
    for line in _STORE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if scenario is None or rec.get("scenario") == scenario:
                records.append(rec)
        except json.JSONDecodeError:
            pass

    records.reverse()           # file is oldest-first; return newest-first
    return records[:limit]


def get_run(run_id: str) -> dict[str, Any] | None:
    """Return a single run record by run_id, or None if not found."""
    if not _STORE_PATH.exists():
        return None

    with _STORE_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("run_id") == run_id:
                    return rec
            except json.JSONDecodeError:
                pass
    return None


def list_scenarios_with_counts() -> list[dict[str, Any]]:
    """Return each scenario name and how many times it has been run."""
    if not _STORE_PATH.exists():
        return []

    counts: dict[str | None, int] = {}
    for line in _STORE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            sc = rec.get("scenario")
            counts[sc] = counts.get(sc, 0) + 1
        except json.JSONDecodeError:
            pass

    return [
        {"scenario": sc or "free_form", "run_count": cnt}
        for sc, cnt in sorted(counts.items(), key=lambda x: -x[1])
    ]
