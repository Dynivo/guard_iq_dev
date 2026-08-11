"""Insights — optimization signals only (never auto-apply)."""

from __future__ import annotations

import uuid

from app.modules.analytics.application.store import InMemoryObservabilityStore
from app.modules.analytics.domain.models import EvaluationResult, OptimizationSignal


class InsightsEngine:
    def __init__(self, store: InMemoryObservabilityStore) -> None:
        self._store = store

    def emit(self, signal: OptimizationSignal) -> None:
        self._store.signals.append(signal)

    def from_evaluation(self, result: EvaluationResult) -> list[OptimizationSignal]:
        created: list[OptimizationSignal] = []
        for kind in result.signals:
            severity = "high" if kind in {"high_edit_distance", "high_latency"} else "medium"
            signal = OptimizationSignal(
                signal_id=str(uuid.uuid4()),
                organization_id=result.organization_id,
                kind=kind,
                severity=severity,
                message=f"Optimization signal: {kind}",
                correlation_id=result.correlation_id,
                metadata={"evaluation_id": result.evaluation_id, "overall": result.overall},
            )
            self.emit(signal)
            created.append(signal)
        return created

    def list_signals(self, org_id: uuid.UUID) -> list[dict]:
        return [s.to_dict() for s in self._store.signals if s.organization_id == org_id]
