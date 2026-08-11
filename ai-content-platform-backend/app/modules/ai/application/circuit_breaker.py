"""Simple in-process circuit breaker per provider."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _BreakerState:
    failures: int = 0
    opened_at: float | None = None


@dataclass
class CircuitBreakerRegistry:
    """Tracks open circuits per provider name."""

    _states: dict[str, _BreakerState] = field(default_factory=dict)

    def is_open(self, provider: str, *, failure_threshold: int, recovery_timeout_ms: int) -> bool:
        state = self._states.get(provider)
        if state is None or state.opened_at is None:
            return False
        elapsed_ms = (time.monotonic() - state.opened_at) * 1000
        if elapsed_ms >= recovery_timeout_ms:
            # half-open: allow one attempt
            state.opened_at = None
            state.failures = 0
            return False
        return True

    def record_success(self, provider: str) -> None:
        self._states[provider] = _BreakerState()

    def record_failure(self, provider: str, *, failure_threshold: int) -> None:
        state = self._states.setdefault(provider, _BreakerState())
        state.failures += 1
        if state.failures >= failure_threshold:
            state.opened_at = time.monotonic()
