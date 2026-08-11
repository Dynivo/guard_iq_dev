"""Correlation Engine — join traces/evals/costs by correlation_id."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.analytics.application.store import InMemoryObservabilityStore


class CorrelationEngine:
    def __init__(self, store: InMemoryObservabilityStore) -> None:
        self._store = store

    def explore(self, org_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "organization_id": str(org_id),
            "ai_traces": self._store.list_ai_traces(org_id, correlation_id=correlation_id),
            "workflow_traces": self._store.list_workflow_traces(
                org_id, correlation_id=correlation_id
            ),
            "evaluations": [
                e.to_dict()
                for e in self._store.evaluations
                if e.organization_id == org_id and e.correlation_id == correlation_id
            ],
            "costs": [
                c.to_dict()
                for c in self._store.costs
                if c.organization_id == org_id and c.correlation_id == correlation_id
            ],
            "signals": [
                s.to_dict()
                for s in self._store.signals
                if s.organization_id == org_id and s.correlation_id == correlation_id
            ],
        }
