"""Brand Intelligence domain events."""

from __future__ import annotations

import uuid
from typing import Any

from app.shared.events.types import DomainEvent


def brand_import_started(
    *,
    organization_id: uuid.UUID,
    correlation_id: str,
    import_id: uuid.UUID,
    profile_id: uuid.UUID,
) -> DomainEvent:
    return DomainEvent(
        event_type="BrandImportStarted",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={"import_id": str(import_id), "profile_id": str(profile_id)},
    )


def brand_import_completed(
    *,
    organization_id: uuid.UUID,
    correlation_id: str,
    import_id: uuid.UUID,
    stage: str,
    success: bool,
    extra: dict[str, Any] | None = None,
) -> DomainEvent:
    payload: dict[str, Any] = {
        "import_id": str(import_id),
        "stage": stage,
        "success": success,
    }
    if extra:
        payload.update(extra)
    return DomainEvent(
        event_type="BrandImportCompleted",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload=payload,
    )


def brand_memory_built(
    *,
    organization_id: uuid.UUID,
    correlation_id: str,
    memory_id: uuid.UUID,
    profile_id: uuid.UUID,
    version_no: int,
    confidence: float,
) -> DomainEvent:
    return DomainEvent(
        event_type="BrandMemoryBuilt",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={
            "memory_id": str(memory_id),
            "profile_id": str(profile_id),
            "version_no": version_no,
            "confidence": confidence,
        },
    )
