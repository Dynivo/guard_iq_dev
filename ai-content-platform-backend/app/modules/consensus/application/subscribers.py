"""EventBus subscribers — adjust provider writing weights from review outcomes."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.consensus.application.weights import InMemoryProviderWeightStore
from app.shared.events.ports import EventBus
from app.shared.events.types import DomainEvent

logger = get_logger(__name__)

_WEIGHT_EVENTS = ("DraftApproved", "DraftRejected", "DraftEdited")


def register_consensus_handlers(
    bus: EventBus,
    weight_store: InMemoryProviderWeightStore | None = None,
) -> InMemoryProviderWeightStore:
    """Subscribe weight learning — mirrors analytics subscriber registration style."""

    store = weight_store or InMemoryProviderWeightStore()

    async def _handle(event: DomainEvent) -> None:
        try:
            providers = _providers_from_event(event)
            if not providers:
                logger.info(
                    "consensus.weight_event_skipped",
                    extra={
                        "app_module": "consensus",
                        "operation": "handle_domain_event",
                        "event_type": event.event_type,
                        "correlation_id": event.correlation_id,
                        "reason": "no_provider",
                        "outcome": "skipped",
                    },
                )
                return

            if event.event_type == "DraftApproved":
                delta_w = store.approve_delta
                delta_s = abs(store.approve_delta)
            elif event.event_type == "DraftRejected":
                delta_w = store.reject_delta
                delta_s = store.reject_delta
            else:  # DraftEdited
                delta_w = store.edit_delta
                delta_s = store.edit_delta

            for provider in providers:
                store.update(
                    provider,
                    delta_writing=delta_w,
                    delta_success=delta_s,
                )

            logger.info(
                "consensus.handled_event",
                extra={
                    "app_module": "consensus",
                    "operation": "handle_domain_event",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "organization_id": str(event.organization_id),
                    "providers": providers,
                    "outcome": "success",
                },
            )
        except Exception as exc:  # noqa: BLE001 — never fail publishers
            logger.error(
                "consensus.handler_error",
                extra={
                    "app_module": "consensus",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "error": str(exc),
                    "outcome": "failure",
                },
            )

    for event_type in _WEIGHT_EVENTS:
        bus.subscribe(event_type, _handle)

    bus._consensus_weight_store = store  # type: ignore[attr-defined]
    return store


def _providers_from_event(event: DomainEvent) -> list[str]:
    payload: dict[str, Any] = dict(event.payload or {})
    found: list[str] = []

    single = payload.get("provider") or payload.get("generation_provider")
    if single:
        found.append(str(single).lower())

    for key in ("providers", "panel", "consensus_panel"):
        values = payload.get(key)
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and item.get("provider"):
                    found.append(str(item["provider"]).lower())
                elif item:
                    found.append(str(item).lower())

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for name in found:
        name = name.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return unique
