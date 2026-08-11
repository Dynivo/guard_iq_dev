"""Provider health scoring on top of circuit breakers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.modules.ai.application.circuit_breaker import CircuitBreakerRegistry


@dataclass
class ProviderHealthStats:
    successes: int = 0
    failures: int = 0
    total_latency_ms: int = 0
    last_error: str = ""
    last_success_at: float | None = None
    last_failure_at: float | None = None

    @property
    def availability(self) -> float:
        total = self.successes + self.failures
        if total == 0:
            return 1.0
        return self.successes / total

    @property
    def avg_latency_ms(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_latency_ms / self.successes

    def health_score(self, *, circuit_open: bool) -> float:
        if circuit_open:
            return 0.0
        # Weighted: availability 70%, latency penalty 30%
        avail = self.availability
        latency_penalty = min(1.0, self.avg_latency_ms / 10_000.0)
        return round(max(0.0, avail * 0.7 + (1.0 - latency_penalty) * 0.3), 4)


@dataclass
class ProviderHealthRegistry:
    breaker: CircuitBreakerRegistry = field(default_factory=CircuitBreakerRegistry)
    _stats: dict[str, ProviderHealthStats] = field(default_factory=dict)

    def _stat(self, provider: str) -> ProviderHealthStats:
        return self._stats.setdefault(provider, ProviderHealthStats())

    def record_success(self, provider: str, *, latency_ms: int) -> None:
        st = self._stat(provider)
        st.successes += 1
        st.total_latency_ms += latency_ms
        st.last_success_at = time.monotonic()
        self.breaker.record_success(provider)

    def record_failure(self, provider: str, *, error: str, failure_threshold: int) -> None:
        st = self._stat(provider)
        st.failures += 1
        st.last_error = error
        st.last_failure_at = time.monotonic()
        self.breaker.record_failure(provider, failure_threshold=failure_threshold)

    def snapshot(self, provider: str, *, failure_threshold: int, recovery_timeout_ms: int) -> dict:
        st = self._stat(provider)
        open_ = self.breaker.is_open(
            provider,
            failure_threshold=failure_threshold,
            recovery_timeout_ms=recovery_timeout_ms,
        )
        return {
            "provider": provider,
            "availability": st.availability,
            "avg_latency_ms": st.avg_latency_ms,
            "failures": st.failures,
            "successes": st.successes,
            "circuit_open": open_,
            "health_score": st.health_score(circuit_open=open_),
            "last_error": st.last_error,
        }
