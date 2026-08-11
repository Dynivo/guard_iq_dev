"""Provider Intelligence — availability, latency, failures, error classes."""

from __future__ import annotations

from app.modules.analytics.domain.models import AITrace, ProviderHealth, TraceStatus
from app.shared.events.types import DomainEvent


class ProviderIntelligence:
    def __init__(self) -> None:
        self._by_provider: dict[str, ProviderHealth] = {}

    def _get(self, provider: str, org_id=None) -> ProviderHealth:
        key = provider or "unknown"
        if key not in self._by_provider:
            self._by_provider[key] = ProviderHealth(provider=key, organization_id=org_id)
        return self._by_provider[key]

    def observe_trace(self, trace: AITrace) -> ProviderHealth:
        health = self._get(trace.provider or "unknown", trace.organization_id)
        health.requests += 1
        health.total_latency_ms += trace.latency_ms
        if trace.status == TraceStatus.SUCCESS:
            health.successes += 1
        elif trace.status == TraceStatus.TIMEOUT:
            health.timeouts += 1
            health.failures += 1
        else:
            if trace.status == TraceStatus.FAILURE:
                health.failures += 1
        if trace.retry_count > 0:
            health.fallbacks += 0  # retries tracked separately
        return health

    def observe_failure(self, event: DomainEvent) -> ProviderHealth:
        payload = event.payload or {}
        provider = str(payload.get("provider") or "unknown")
        health = self._get(provider, event.organization_id)
        health.requests += 1
        health.failures += 1
        err = str(payload.get("error_class") or payload.get("error_message") or "unknown")
        # Normalize to short class
        err_class = err.split(":")[0][:80]
        health.error_classes[err_class] = health.error_classes.get(err_class, 0) + 1
        if "timeout" in err.lower():
            health.timeouts += 1
        if payload.get("fallback_used"):
            health.fallbacks += 1
        return health

    def list_health(self) -> list[dict]:
        return [h.to_dict() for h in self._by_provider.values()]

    def get(self, provider: str) -> dict | None:
        h = self._by_provider.get(provider)
        return h.to_dict() if h else None
