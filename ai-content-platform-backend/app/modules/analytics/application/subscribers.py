"""EventBus subscribers for non-blocking analytics collection."""

from __future__ import annotations

from app.core.logging import get_logger
from app.modules.analytics.application.runtime import (
    get_observability_engine,
    set_observability_engine,
)
from app.shared.events.ports import EventBus
from app.shared.events.types import DomainEvent

logger = get_logger(__name__)

_OBSERVED_EVENTS = (
    "DraftGenerated",
    "DraftApproved",
    "DraftRejected",
    "DraftEdited",
    "ImageGenerated",
    "CarouselGenerated",
    "ArticleImported",
    "PromptEvaluated",
    "ProviderFailed",
    "WorkflowStarted",
    "WorkflowCompleted",
    "WorkflowFailed",
    "WorkflowCancelled",
    "NodeStarted",
    "NodeCompleted",
    "NodeFailed",
)


def register_analytics_handlers(
    bus: EventBus, engine=None
) -> None:
    """Subscribe ObservabilityEngine — never blocks generation paths by design."""

    obs = engine or get_observability_engine()
    set_observability_engine(obs)

    async def _handle(event: DomainEvent) -> None:
        try:
            await obs.handle_domain_event(event)
            logger.info(
                "analytics.handled_event",
                extra={
                    "app_module": "analytics",
                    "operation": "handle_domain_event",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "organization_id": str(event.organization_id),
                    "outcome": "success",
                },
            )
        except Exception as exc:  # noqa: BLE001 — never fail publishers
            logger.error(
                "analytics.handler_error",
                extra={
                    "app_module": "analytics",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )

    for event_type in _OBSERVED_EVENTS:
        bus.subscribe(event_type, _handle)

    # Attach engine for tests / API reuse
    bus._analytics_engine = obs  # type: ignore[attr-defined]
