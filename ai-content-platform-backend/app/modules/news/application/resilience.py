"""Resilience — rate limits, circuit breakers, health monitor."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.modules.news.domain.models import CircuitState, SourceHealth


class InMemoryRateLimitManager:
    def __init__(self, *, max_calls: int = 60, window_seconds: float = 60.0) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self._window:
            q.popleft()
        return len(q) < self._max

    def record(self, key: str) -> None:
        self._hits[key].append(time.monotonic())


class InMemoryCircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, cooldown_seconds: float = 60.0) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failures: dict[str, int] = defaultdict(int)
        self._opened_at: dict[str, float] = {}
        self._state: dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)

    def allow(self, key: str) -> bool:
        state = self._state[key]
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at.get(key, 0) >= self._cooldown:
                self._state[key] = CircuitState.HALF_OPEN
                return True
            return False
        return True  # half-open: allow probe

    def record_success(self, key: str) -> None:
        self._failures[key] = 0
        self._state[key] = CircuitState.CLOSED
        self._opened_at.pop(key, None)

    def record_failure(self, key: str) -> None:
        self._failures[key] += 1
        if self._failures[key] >= self._threshold:
            self._state[key] = CircuitState.OPEN
            self._opened_at[key] = time.monotonic()


class InMemoryHealthMonitor:
    def __init__(self) -> None:
        self._success: dict[str, int] = defaultdict(int)
        self._failure: dict[str, int] = defaultdict(int)
        self._latency: dict[str, float] = {}
        self._last_error: dict[str, str] = {}
        self._breaker = InMemoryCircuitBreaker()

    def record_success(self, source_id: str, latency_ms: float) -> None:
        self._success[source_id] += 1
        self._latency[source_id] = latency_ms
        self._breaker.record_success(source_id)

    def record_failure(self, source_id: str, error: str) -> None:
        self._failure[source_id] += 1
        self._last_error[source_id] = error
        self._breaker.record_failure(source_id)

    def get(self, source_id: str) -> SourceHealth:
        total = self._success[source_id] + self._failure[source_id]
        rate = self._failure[source_id] / total if total else 0.0
        return SourceHealth(
            source_id=source_id,
            healthy=self._breaker.allow(source_id) and rate < 0.5,
            circuit_state=self._breaker._state[source_id],
            failure_rate=rate,
            last_error=self._last_error.get(source_id, ""),
            latency_ms=self._latency.get(source_id, 0.0),
        )
