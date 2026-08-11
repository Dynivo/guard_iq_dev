"""Event bus factory — singleton InProcessEventBus (replaceable later)."""

from __future__ import annotations

from functools import lru_cache

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.shared.events.ports import EventBus


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    return InProcessEventBus()


def clear_event_bus_cache() -> None:
    get_event_bus.cache_clear()
