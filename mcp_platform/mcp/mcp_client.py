"""
MCPClient — thin facade over the 2 MCP tools.

Exposes a single, clean interface to ImprovementActionAgent so the agent
does not need to know about tool internals or timeout handling.

Both tools degrade gracefully when ChromaDB is unavailable:
  search_interventions  → returns []
  get_best_practices    → returns built-in fallback BestPractice

Timeout: asyncio.wait_for wraps each tool call. Default 10 s (from settings).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from configs.settings import settings
from mcp_platform.mcp.tools.fetch_best_practices import BestPractice, fetch_best_practices_by_issue
from mcp_platform.mcp.tools.search_similar_interventions import CaseStudy, search_similar_interventions

logger = logging.getLogger(__name__)

# Re-export domain types so callers can import from one place
__all__ = ["MCPClient", "CaseStudy", "BestPractice"]


class MCPClient:
    """Facade that wraps both MCP tools with a consistent timeout + error boundary."""

    def __init__(self, timeout_seconds: float | None = None) -> None:
        self._timeout = timeout_seconds if timeout_seconds is not None else float(
            getattr(settings, "mcp_timeout_seconds", 10)
        )

    # ── Tool 1 ───────────────────────────────────────────────────────────────────

    async def search_interventions(
        self,
        issue: str,
        role: str | None = None,
        n_results: int = 3,
    ) -> list[CaseStudy]:
        """Return past case studies that match the described hiring issue.

        Returns [] on timeout or ChromaDB failure — caller handles empty gracefully.
        """
        try:
            return await asyncio.wait_for(
                search_similar_interventions(issue, role=role, n_results=n_results),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool 1 timed out (%.0f s) for issue: %.60s", self._timeout, issue)
            return []
        except Exception as exc:
            logger.error("MCP tool 1 error: %s", exc)
            return []

    # ── Tool 2 ───────────────────────────────────────────────────────────────────

    async def get_best_practices(self, issue: str) -> list[BestPractice]:
        """Return structured best-practice entries for the described hiring problem.

        Falls back to built-in practices on timeout or ChromaDB failure.
        """
        try:
            return await asyncio.wait_for(
                fetch_best_practices_by_issue(issue),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool 2 timed out (%.0f s) for issue: %.60s", self._timeout, issue)
            # Still return fallback — never leave the agent with no best practices
            try:
                from mcp_platform.mcp.tools.fetch_best_practices import _FALLBACK_PRACTICES
                return list(_FALLBACK_PRACTICES.values())[:1]
            except Exception:
                return []
        except Exception as exc:
            logger.error("MCP tool 2 error: %s", exc)
            return []

    # ── Convenience: fetch both in parallel ─────────────────────────────────────

    async def fetch_evidence(
        self,
        issue: str,
        role: str | None = None,
    ) -> tuple[list[CaseStudy], list[BestPractice]]:
        """Call both tools concurrently and return (case_studies, best_practices)."""
        case_studies, practices = await asyncio.gather(
            self.search_interventions(issue, role=role),
            self.get_best_practices(issue),
        )
        return case_studies, practices
