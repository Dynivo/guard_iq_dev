"""In-process async event bus — default EventBus adapter."""

from __future__ import annotations

from collections import defaultdict

from app.core.logging import get_logger
from app.core.observability.correlation import reset_correlation_id, set_correlation_id
from app.shared.events.ports import EventHandler
from app.shared.events.types import DomainEvent

logger = get_logger(__name__)


class InProcessEventBus:
    """Synchronous fan-out within the process. Replaceable with Redis/queue later."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.info(
            "event_bus.subscribe",
            extra={
                "app_module": "events",
                "operation": "subscribe",
                "event_type": event_type,
            },
        )

    async def publish(self, event: DomainEvent) -> None:
        token = set_correlation_id(event.correlation_id)
        handlers = list(self._handlers.get(event.event_type, []))
        logger.info(
            "event_bus.publish",
            extra={
                "app_module": "events",
                "operation": "publish",
                "event_type": event.event_type,
                "event_id": str(event.event_id),
                "organization_id": str(event.organization_id),
                "correlation_id": event.correlation_id,
                "handler_count": len(handlers),
                "outcome": "started",
            },
        )
        errors: list[Exception] = []
        try:
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "event_bus.handler_failed",
                        extra={
                            "app_module": "events",
                            "operation": "handle",
                            "event_type": event.event_type,
                            "correlation_id": event.correlation_id,
                            "outcome": "failure",
                        },
                    )
                    errors.append(exc)
        finally:
            reset_correlation_id(token)

        if errors:
            raise errors[0]
