"""
Abstract base class for all ATS workflows.

A workflow translates a high-level user request into one or more
CoordinatorAgent pipeline runs and returns a CoordinatorResponse.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agents.coordinator.response_assembler import CoordinatorResponse
from shared.contracts.coordinator_request import CoordinatorRequest


class BaseWorkflow(ABC):
    """All concrete workflows inherit this."""

    @abstractmethod
    async def run(self, request: CoordinatorRequest) -> CoordinatorResponse:
        """Execute the workflow for a free-form or scenario-tagged request."""

    @abstractmethod
    async def run_scenario(
        self,
        name: str,
        filters: dict[str, Any],
        structured_data: dict[str, Any],
    ) -> CoordinatorResponse:
        """Execute a named scenario with caller-supplied data and filters."""

    @abstractmethod
    def scenario_names(self) -> list[str]:
        """Return the list of scenario names this workflow supports."""
