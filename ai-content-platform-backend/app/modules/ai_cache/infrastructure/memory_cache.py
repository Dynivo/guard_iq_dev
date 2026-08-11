"""In-memory AI cache adapter."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _Entry:
    value: dict
    expires_at: float


class InMemoryAICache:
    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    async def get(self, key: str) -> dict | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at and entry.expires_at < time.time():
            self._store.pop(key, None)
            return None
        return dict(entry.value)

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        expires = time.time() + max(0, ttl_seconds) if ttl_seconds else 0.0
        self._store[key] = _Entry(value=dict(value), expires_at=expires)

    async def invalidate(self, prefix: str) -> None:
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            self._store.pop(k, None)
