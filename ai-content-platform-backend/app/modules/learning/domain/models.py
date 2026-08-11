"""Learning domain models — events and knowledge artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class LearningArtifactKind(StrEnum):
    EXAMPLE = "example"
    NEGATIVE_RULE = "negative_rule"
    WRITING_PREFERENCE = "writing_preference"
    BRAND_PREFERENCE = "brand_preference"
    KNOWLEDGE_SIGNAL = "knowledge_signal"
    RECOMMENDATION = "recommendation"


class KnowledgeLifecycle(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass(slots=True)
class LearningEvent:
    id: UUID
    organization_id: UUID
    source_event_type: str
    correlation_id: str
    draft_id: UUID | None = None
    review_session_id: UUID | None = None
    feedback_event_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    captured_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "source_event_type": self.source_event_type,
            "correlation_id": self.correlation_id,
            "draft_id": str(self.draft_id) if self.draft_id else None,
            "review_session_id": str(self.review_session_id) if self.review_session_id else None,
            "feedback_event_id": str(self.feedback_event_id) if self.feedback_event_id else None,
            "payload": dict(self.payload),
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
        }


@dataclass(slots=True)
class KnowledgeArtifact:
    kind: LearningArtifactKind
    organization_id: UUID
    body: str
    category: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    approval_count: int = 0
    usage_count: int = 0
    success_rate: float = 0.0
    created_from_review: bool = True
    last_used: datetime | None = None
    lifecycle: KnowledgeLifecycle = KnowledgeLifecycle.CANDIDATE
    source_learning_event_id: UUID | None = None
    version: int = 1
    supersedes_id: UUID | None = None

    @property
    def is_active(self) -> bool:
        return self.lifecycle == KnowledgeLifecycle.APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "organization_id": str(self.organization_id),
            "body": self.body,
            "category": self.category,
            "metadata": dict(self.metadata),
            "confidence": self.confidence,
            "approval_count": self.approval_count,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_from_review": self.created_from_review,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "lifecycle": str(self.lifecycle),
            "is_active": self.is_active,
            "source_learning_event_id": (
                str(self.source_learning_event_id) if self.source_learning_event_id else None
            ),
            "version": self.version,
            "supersedes_id": str(self.supersedes_id) if self.supersedes_id else None,
        }


@dataclass(slots=True)
class PreferenceUpdate:
    id: UUID
    organization_id: UUID
    preference_id: UUID | None
    previous_text: str | None
    new_text: str
    category: str
    source_learning_event_id: UUID | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "preference_id": str(self.preference_id) if self.preference_id else None,
            "previous_text": self.previous_text,
            "new_text": self.new_text,
            "category": self.category,
            "source_learning_event_id": (
                str(self.source_learning_event_id) if self.source_learning_event_id else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
