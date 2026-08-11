"""AI Orchestrator ports."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.modules.ai.domain.models import OrchestratorRequest, OrchestratorResult, StreamChunk
from app.shared.ai_types import CompletionResult


class CostEstimator(Protocol):
    def estimate(
        self,
        *,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> float: ...


class AIOrchestrator(Protocol):
    async def execute(self, request: OrchestratorRequest) -> OrchestratorResult: ...

    async def execute_stream(
        self, request: OrchestratorRequest
    ) -> AsyncIterator[StreamChunk]: ...

    async def execute_many(
        self, requests: list[OrchestratorRequest]
    ) -> list[OrchestratorResult]: ...

    async def complete(
        self,
        capability: str,
        prompt: str,
        **overrides,
    ) -> CompletionResult:
        """Convenience API compatible with legacy ProviderManager.complete."""
        ...
