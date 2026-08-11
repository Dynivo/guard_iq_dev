"""Materialize learning signals into examples, rules, preferences.

Evolves to Capture → Process → Store while preserving the EventBus entry API.
Never rewrites prompts — structured knowledge artifacts only.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.application.capture import LearningCapture
from app.modules.learning.application.processor import LearningProcessor
from app.modules.learning.application.store import SessionLearningStore
from app.modules.learning.domain.models import LearningArtifactKind
from app.shared.events.types import DomainEvent


class LearningMaterializer:
    def __init__(
        self,
        session: AsyncSession,
        *,
        config_dir: str | None = None,
        capture: LearningCapture | None = None,
        processor: LearningProcessor | None = None,
        store: SessionLearningStore | None = None,
    ) -> None:
        self._session = session
        self._capture = capture or LearningCapture(config_dir)
        self._processor = processor or LearningProcessor(config_dir)
        self._store = store or SessionLearningStore(session, config_dir=config_dir)
        self.last_result: dict[str, Any] | None = None

    async def on_approve_payload(
        self,
        org_id: uuid.UUID,
        *,
        draft_id: uuid.UUID,
        content_type: str,
        text: str,
        hook: str | None,
    ) -> None:
        from app.shared.events.types import draft_approved

        event = draft_approved(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=uuid.UUID(int=0),
            feedback_event_id=uuid.UUID(int=0),
            content_type=content_type,
            text=text,
            hook=hook,
            correlation_id="materialize-direct",
        )
        await self.handle_domain_event(event)

    async def on_reject_payload(
        self,
        org_id: uuid.UUID,
        *,
        feedback_id: uuid.UUID,
        category: str,
        reason: str,
    ) -> None:
        from app.shared.events.types import draft_rejected

        event = draft_rejected(
            organization_id=org_id,
            draft_id=uuid.UUID(int=0),
            user_id=uuid.UUID(int=0),
            feedback_event_id=feedback_id,
            category=category,
            reason=reason,
            correlation_id="materialize-direct",
        )
        await self.handle_domain_event(event)

    async def on_edit_payload(
        self,
        org_id: uuid.UUID,
        *,
        original: str,
        edited: str,
    ) -> None:
        from app.shared.events.types import draft_edited

        event = draft_edited(
            organization_id=org_id,
            draft_id=uuid.UUID(int=0),
            user_id=uuid.UUID(int=0),
            feedback_event_id=uuid.UUID(int=0),
            original_text=original,
            edited_text=edited,
            correlation_id="materialize-direct",
        )
        await self.handle_domain_event(event)

    async def handle_domain_event(self, event: DomainEvent) -> None:
        le = self._capture.capture(event)
        if le is None:
            self.last_result = {"captured": False}
            return
        self._store.learning_events.append(le.to_dict())
        artifacts = self._processor.process(le)
        # Persist only durable library kinds via Session store
        durable = [
            a
            for a in artifacts
            if a.kind
            in {
                LearningArtifactKind.EXAMPLE,
                LearningArtifactKind.NEGATIVE_RULE,
                LearningArtifactKind.WRITING_PREFERENCE,
                LearningArtifactKind.BRAND_PREFERENCE,
                LearningArtifactKind.KNOWLEDGE_SIGNAL,
            }
        ]
        stored = await self._store.store(durable)
        self.last_result = {
            "captured": True,
            "learning_event_id": str(le.id),
            "artifact_count": len(artifacts),
            "stored": stored,
        }
