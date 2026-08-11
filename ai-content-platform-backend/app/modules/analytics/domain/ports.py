"""Analytics module ports."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.modules.analytics.domain.models import (
    AITrace,
    CostRecord,
    EvaluationResult,
    ModelHealth,
    OptimizationSignal,
    ProviderHealth,
    WorkflowTrace,
)
from app.shared.events.types import DomainEvent


class ObservabilityStorePort(Protocol):
    async def store_ai_trace(self, trace: AITrace) -> None: ...

    async def store_workflow_trace(self, trace: WorkflowTrace) -> None: ...

    async def store_evaluation(self, result: EvaluationResult) -> None: ...

    async def store_cost(self, record: CostRecord) -> None: ...

    def list_ai_traces(
        self, org_id: uuid.UUID, *, correlation_id: str | None = None
    ) -> list[dict[str, Any]]: ...


class MetricsExporterPort(Protocol):
    """Prometheus-compatible export surface (thin; full ops exporters M15)."""

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None: ...

    def observe(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None: ...

    def snapshot(self) -> dict[str, Any]: ...


class AnalyticsEventHandlerPort(Protocol):
    async def handle(self, event: DomainEvent) -> None: ...


class InsightsPort(Protocol):
    def emit(self, signal: OptimizationSignal) -> None: ...

    def list_signals(self, org_id: uuid.UUID) -> list[OptimizationSignal]: ...
