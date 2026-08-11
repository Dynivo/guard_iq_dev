"""Event bus port — replaceable (in-process today; Redis/queue later)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.shared.events.types import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

    def subscribe(self, event_type: str, handler: EventHandler) -> None: ...
