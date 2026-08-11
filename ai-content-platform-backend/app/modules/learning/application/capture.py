"""LearningCapture — normalize review domain events → LearningEvent."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.learning.application.config_loader import load_learning_config
from app.modules.learning.domain.models import LearningEvent
from app.shared.events.types import DomainEvent


class LearningCapture:
    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_learning_config(config_dir)

    def allowed_types(self) -> set[str]:
        cap = (self._config.get("capture") or {}).get("capture") or {}
        return {str(t) for t in (cap.get("event_types") or [])}

    def capture(self, event: DomainEvent) -> LearningEvent | None:
        allowed = self.allowed_types()
        if allowed and event.event_type not in allowed:
            return None
        payload = dict(event.payload or {})
        draft_raw = payload.get("draft_id")
        session_raw = payload.get("review_session_id")
        feedback_raw = payload.get("feedback_event_id")
        return LearningEvent(
            id=uuid.uuid4(),
            organization_id=event.organization_id,
            source_event_type=event.event_type,
            correlation_id=event.correlation_id,
            draft_id=uuid.UUID(str(draft_raw)) if draft_raw else None,
            review_session_id=uuid.UUID(str(session_raw)) if session_raw else None,
            feedback_event_id=uuid.UUID(str(feedback_raw)) if feedback_raw else None,
            payload=payload,
            captured_at=datetime.now(timezone.utc),
        )
