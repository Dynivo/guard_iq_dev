"""AI Trace Engine — record AI request observability traces."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.analytics.application.store import InMemoryObservabilityStore
from app.modules.analytics.domain.models import AITrace, TraceStatus
from app.shared.events.types import DomainEvent


class AITraceEngine:
    def __init__(self, store: InMemoryObservabilityStore) -> None:
        self._store = store

    async def record(self, trace: AITrace) -> AITrace:
        if trace.occurred_at is None:
            trace.occurred_at = datetime.now(timezone.utc)
        await self._store.store_ai_trace(trace)
        return trace

    async def from_domain_event(self, event: DomainEvent) -> AITrace:
        payload = event.payload or {}
        status = TraceStatus.SUCCESS
        if event.event_type == "ProviderFailed":
            status = TraceStatus.FAILURE
        trace = AITrace(
            request_id=str(payload.get("request_id") or event.event_id),
            correlation_id=event.correlation_id,
            organization_id=event.organization_id,
            workflow_id=payload.get("workflow_id"),
            provider=payload.get("provider"),
            model=payload.get("model"),
            capability=payload.get("capability"),
            user_id=payload.get("user_id"),
            latency_ms=int(payload.get("latency_ms") or 0),
            tokens_in=int(payload.get("tokens_in") or 0),
            tokens_out=int(payload.get("tokens_out") or 0),
            cache_hit=bool(payload.get("cache_hit") or False),
            retry_count=int(payload.get("retry_count") or 0),
            status=status,
            event_type=event.event_type,
            cost_estimate=float(payload.get("cost_estimate") or 0.0),
            metadata=dict(payload),
            occurred_at=event.occurred_at,
        )
        return await self.record(trace)

    def list_for_org(
        self, org_id: uuid.UUID, *, correlation_id: str | None = None
    ) -> list[dict]:
        return self._store.list_ai_traces(org_id, correlation_id=correlation_id)
