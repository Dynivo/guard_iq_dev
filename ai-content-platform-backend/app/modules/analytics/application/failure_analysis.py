"""Failure Analysis — error class taxonomy from provider/workflow failures."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.shared.events.types import DomainEvent


class FailureAnalysis:
    def __init__(self) -> None:
        self._classes: dict[str, int] = defaultdict(int)
        self._events: list[dict[str, Any]] = []

    def classify(self, event: DomainEvent) -> str:
        payload = event.payload or {}
        msg = str(payload.get("error_message") or payload.get("error") or event.event_type)
        lower = msg.lower()
        if "timeout" in lower:
            cls = "timeout"
        elif "rate" in lower or "429" in lower:
            cls = "rate_limit"
        elif "auth" in lower or "401" in lower or "403" in lower:
            cls = "auth"
        elif "validation" in lower or "invalid" in lower:
            cls = "validation"
        elif event.event_type.endswith("Failed"):
            cls = "provider_failed" if "Provider" in event.event_type else "workflow_failed"
        else:
            cls = "unknown"
        self._classes[cls] += 1
        self._events.append(
            {
                "class": cls,
                "event_type": event.event_type,
                "correlation_id": event.correlation_id,
                "organization_id": str(event.organization_id),
                "message": msg[:200],
            }
        )
        return cls

    def summary(self) -> dict[str, Any]:
        return {"error_classes": dict(self._classes), "recent": self._events[-50:]}
