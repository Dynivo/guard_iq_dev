"""Learning module event subscribers — Review must not call Learning directly."""

from __future__ import annotations

from app.core.logging import get_logger
from app.modules.learning.application.materialize import LearningMaterializer
from app.shared.events.ports import EventBus
from app.shared.events.session_context import get_event_session
from app.shared.events.types import DomainEvent

logger = get_logger(__name__)


def register_learning_handlers(bus: EventBus, session_factory=None) -> None:
    """Subscribe LearningMaterializer to review lifecycle events.

    Prefers the request-scoped session from event session context (same UoW as
    the publisher). Falls back to session_factory when no context is bound.
    """

    async def _handle(event: DomainEvent) -> None:
        session = get_event_session()
        if session is not None:
            materializer = LearningMaterializer(session)
            await materializer.handle_domain_event(event)
            logger.info(
                "learning.handled_event",
                extra={
                    "app_module": "learning",
                    "operation": "handle_domain_event",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "organization_id": str(event.organization_id),
                    "outcome": "success",
                },
            )
            return

        if session_factory is None:
            raise RuntimeError(
                "No event session context and no session_factory for learning handler"
            )

        async with session_factory() as owned:
            materializer = LearningMaterializer(owned)
            await materializer.handle_domain_event(event)
            await owned.commit()
            logger.info(
                "learning.handled_event",
                extra={
                    "app_module": "learning",
                    "operation": "handle_domain_event",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "organization_id": str(event.organization_id),
                    "outcome": "success",
                },
            )

    for event_type in ("DraftApproved", "DraftRejected", "DraftEdited"):
        bus.subscribe(event_type, _handle)
