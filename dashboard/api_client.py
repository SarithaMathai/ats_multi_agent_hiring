"""
Thin synchronous httpx wrapper around the FastAPI backend.

Streamlit runs in a synchronous context, so all calls use httpx.Client (not
AsyncClient).  A short connect timeout prevents the UI from hanging when the
backend is offline; a longer read timeout accommodates multi-agent LLM runs.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from dashboard.config import API_BASE_URL, API_TIMEOUT

logger = logging.getLogger(__name__)

_OFFLINE_RESPONSE: dict[str, Any] = {
    "status": "error",
    "run_id": "offline",
    "query": "",
    "summary": "Backend is offline. Start the FastAPI server and refresh.",
    "agent_outputs": [],
    "all_recommendations": [],
    "total_tokens": 0,
    "total_latency_ms": 0.0,
    "metadata": {},
}


class ATSApiClient:
    """Calls the FastAPI backend; returns a fallback dict if unreachable."""

    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base,
            timeout=httpx.Timeout(connect=5.0, read=API_TIMEOUT, write=10.0, pool=5.0),
        )

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(
        self,
        query: str,
        scenario: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/analysis/run — free-form or scenario-tagged query."""
        payload: dict[str, Any] = {"query": query, "filters": filters or {}}
        if scenario:
            payload["scenario"] = scenario
        return self._post("/api/v1/analysis/run", payload)

    def run_scenario(
        self,
        name: str,
        structured_data: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
        query_override: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/analysis/scenario/{name} — named scenario with data."""
        payload: dict[str, Any] = {
            "filters": filters or {},
            "structured_data": structured_data or {},
        }
        if query_override:
            payload["query_override"] = query_override
        return self._post(f"/api/v1/analysis/scenario/{name}", payload)

    def list_scenarios(self) -> list[dict[str, Any]]:
        """GET /api/v1/analysis/scenarios — all registered scenarios."""
        try:
            resp = self._client.get("/api/v1/analysis/scenarios")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("list_scenarios failed: %s", exc)
            return []

    def get_run(self, run_id: str) -> dict[str, Any]:
        """GET /api/v1/analysis/runs/{run_id} — retrieve a cached run."""
        try:
            resp = self._client.get(f"/api/v1/analysis/runs/{run_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("get_run(%s) failed: %s", run_id, exc)
            return _OFFLINE_RESPONSE

    # ── Metrics / Reports ─────────────────────────────────────────────────────

    def get_live_metrics(self) -> dict[str, Any]:
        """GET /api/v1/metrics/live — pre-aggregated PostgreSQL data for charts."""
        try:
            resp = self._client.get("/api/v1/metrics/live")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("get_live_metrics failed: %s", exc)
            return {}

    def get_run_history(
        self,
        limit: int = 50,
        scenario: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /api/v1/metrics/runs — run history from JSONL store."""
        params: dict[str, Any] = {"limit": limit}
        if scenario:
            params["scenario"] = scenario
        try:
            resp = self._client.get("/api/v1/metrics/runs", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("get_run_history failed: %s", exc)
            return []

    def get_run_detail(self, run_id: str) -> dict[str, Any]:
        """GET /api/v1/metrics/runs/{run_id} — single run from JSONL store."""
        try:
            resp = self._client.get(f"/api/v1/metrics/runs/{run_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("get_run_detail(%s) failed: %s", run_id, exc)
            return {}

    def get_scenarios_summary(self) -> list[dict[str, Any]]:
        """GET /api/v1/metrics/scenarios/summary — run counts per scenario."""
        try:
            resp = self._client.get("/api/v1/metrics/scenarios/summary")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("get_scenarios_summary failed: %s", exc)
            return []

    # ── Health ────────────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """GET /api/v1/health — overall system health."""
        try:
            resp = self._client.get("/api/v1/health", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("health_check failed: %s", exc)
            return {"status": "error", "checks": [], "detail": str(exc)}

    # ── Private ───────────────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict) -> dict[str, Any]:
        try:
            resp = self._client.post(path, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            logger.error("FastAPI backend unreachable at %s", self._base)
            return {**_OFFLINE_RESPONSE, "query": payload.get("query", "")}
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %d from %s: %s", exc.response.status_code, path, exc.response.text)
            return {
                **_OFFLINE_RESPONSE,
                "summary": f"API error {exc.response.status_code}: {exc.response.text[:200]}",
            }
        except Exception as exc:
            logger.error("Unexpected error calling %s: %s", path, exc)
            return {**_OFFLINE_RESPONSE, "summary": f"Unexpected error: {exc}"}


# Singleton used by all pages
api_client = ATSApiClient()
