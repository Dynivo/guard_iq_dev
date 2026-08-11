"""Model Intelligence — quality, speed, cost, cache, approval aggregates."""

from __future__ import annotations

from app.modules.analytics.domain.models import AITrace, ModelHealth


class ModelIntelligence:
    def __init__(self) -> None:
        self._models: dict[tuple[str, str], ModelHealth] = {}

    def _get(self, provider: str, model: str) -> ModelHealth:
        key = (provider or "unknown", model or "unknown")
        if key not in self._models:
            self._models[key] = ModelHealth(provider=key[0], model=key[1])
        return self._models[key]

    def observe_trace(self, trace: AITrace) -> ModelHealth:
        health = self._get(trace.provider or "unknown", trace.model or "unknown")
        health.requests += 1
        health.total_latency_ms += trace.latency_ms
        health.total_cost += float(trace.cost_estimate or 0.0)
        if trace.cache_hit:
            health.cache_hits += 1
        return health

    def record_approval_score(self, provider: str, model: str, score: float) -> None:
        health = self._get(provider, model)
        health.approval_score_sum += score
        health.approval_score_n += 1

    def record_quality(self, provider: str, model: str, score: float) -> None:
        health = self._get(provider, model)
        health.quality_score_sum += score
        health.quality_score_n += 1

    def record_hallucination(self, provider: str, model: str) -> None:
        health = self._get(provider, model)
        health.hallucination_reports += 1

    def list_health(self) -> list[dict]:
        return [h.to_dict() for h in self._models.values()]
