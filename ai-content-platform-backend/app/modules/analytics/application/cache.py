"""Observability caches — metrics, traces, evaluations."""

from __future__ import annotations

import time
from typing import Any


class ObservabilityCache:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires, value = item
        if time.monotonic() > expires:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)

    def invalidate(self, prefix: str = "") -> None:
        if not prefix:
            self._store.clear()
            return
        for k in list(self._store):
            if k.startswith(prefix):
                del self._store[k]
