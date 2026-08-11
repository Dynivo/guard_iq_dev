"""AI Cache port."""

from __future__ import annotations

from typing import Protocol


class AICachePort(Protocol):
    async def get(self, key: str) -> dict | None: ...

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None: ...

    async def invalidate(self, prefix: str) -> None: ...
