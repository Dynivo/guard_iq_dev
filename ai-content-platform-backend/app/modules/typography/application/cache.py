"""Caches for typography pipeline."""

from __future__ import annotations

from typing import Any


class InMemoryDictCache:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value


class TypographyCacheBundle:
    def __init__(self) -> None:
        self.layout = InMemoryDictCache()
        self.typography = InMemoryDictCache()
        self.brand = InMemoryDictCache()
        self.overlay = InMemoryDictCache()
