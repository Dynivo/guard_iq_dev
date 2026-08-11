"""Trace replay / diff for observability (read-only)."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.analytics.application.store import InMemoryObservabilityStore


class ObservabilityReplayService:
    def __init__(self, store: InMemoryObservabilityStore) -> None:
        self._store = store

    def replay(self, org_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        traces = self._store.list_ai_traces(org_id, correlation_id=correlation_id)
        wf = self._store.list_workflow_traces(org_id, correlation_id=correlation_id)
        return {
            "correlation_id": correlation_id,
            "ai_traces": traces,
            "workflow_traces": wf,
            "count": len(traces) + len(wf),
        }

    def diff_traces(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        keys = set(left) | set(right)
        changed = {}
        for k in keys:
            if left.get(k) != right.get(k):
                changed[k] = {"left": left.get(k), "right": right.get(k)}
        return {"changed_fields": changed, "identical": len(changed) == 0}
