"""Workflow Trace Engine — node lifecycle observability."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.analytics.application.store import InMemoryObservabilityStore
from app.modules.analytics.domain.models import WorkflowTrace
from app.shared.events.types import DomainEvent


class WorkflowTraceEngine:
    def __init__(self, store: InMemoryObservabilityStore) -> None:
        self._store = store

    async def record(self, trace: WorkflowTrace) -> WorkflowTrace:
        if trace.occurred_at is None:
            trace.occurred_at = datetime.now(timezone.utc)
        await self._store.store_workflow_trace(trace)
        return trace

    async def from_domain_event(self, event: DomainEvent) -> WorkflowTrace | None:
        if not event.event_type.startswith("Workflow") and not event.event_type.startswith(
            "Node"
        ):
            # Also accept explicit workflow node payloads
            if "node_id" not in (event.payload or {}):
                return None
        payload = event.payload or {}
        phase = "start" if "Started" in event.event_type else "finish"
        if payload.get("phase"):
            phase = str(payload["phase"])
        trace = WorkflowTrace(
            execution_id=str(payload.get("execution_id") or event.event_id),
            correlation_id=event.correlation_id,
            organization_id=event.organization_id,
            workflow_name=str(payload.get("workflow_name") or "unknown"),
            node_id=str(payload.get("node_id") or payload.get("workflow_name") or "root"),
            phase=phase,
            duration_ms=int(payload.get("duration_ms") or 0),
            failure=bool(payload.get("failure") or event.event_type.endswith("Failed")),
            retry_count=int(payload.get("retry_count") or payload.get("retries") or 0),
            fallback_used=bool(payload.get("fallback_used") or False),
            dependencies=tuple(str(x) for x in (payload.get("dependencies") or ())),
            outcome=payload.get("outcome"),
            metadata=dict(payload),
            occurred_at=event.occurred_at,
        )
        return await self.record(trace)

    def list_for_org(
        self, org_id: uuid.UUID, *, correlation_id: str | None = None
    ) -> list[dict]:
        return self._store.list_workflow_traces(org_id, correlation_id=correlation_id)

    def statistics(self) -> dict:
        return dict(self._store.workflow_stats)
