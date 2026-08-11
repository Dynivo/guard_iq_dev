"""Caches for carousel pipeline."""

from __future__ import annotations

from typing import Any


class InMemoryDictCache:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value


class CarouselCacheBundle:
    def __init__(self) -> None:
        self.deck = InMemoryDictCache()
        self.slide = InMemoryDictCache()
        self.render = InMemoryDictCache()
        self.export = InMemoryDictCache()
