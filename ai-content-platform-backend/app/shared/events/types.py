"""Domain event base and typed lifecycle events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base domain event — all platform events carry org + correlation."""

    event_type: str
    organization_id: uuid.UUID
    correlation_id: str
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=_utcnow)
    payload: dict[str, Any] = field(default_factory=dict)


def draft_generated(
    *,
    organization_id: uuid.UUID,
    draft_id: uuid.UUID,
    article_id: uuid.UUID | None,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="DraftGenerated",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={
            "draft_id": str(draft_id),
            "article_id": str(article_id) if article_id else None,
        },
    )


def draft_approved(
    *,
    organization_id: uuid.UUID,
    draft_id: uuid.UUID,
    user_id: uuid.UUID,
    feedback_event_id: uuid.UUID,
    content_type: str,
    text: str,
    hook: str | None,
    correlation_id: str,
    review_session_id: uuid.UUID | None = None,
    reason_codes: list[str] | None = None,
    version_refs: list[dict[str, Any]] | None = None,
) -> DomainEvent:
    payload: dict[str, Any] = {
        "draft_id": str(draft_id),
        "user_id": str(user_id),
        "feedback_event_id": str(feedback_event_id),
        "content_type": content_type,
        "text": text,
        "hook": hook,
    }
    if review_session_id is not None:
        payload["review_session_id"] = str(review_session_id)
    if reason_codes:
        payload["reason_codes"] = list(reason_codes)
    if version_refs:
        payload["version_refs"] = list(version_refs)
    return DomainEvent(
        event_type="DraftApproved",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload=payload,
    )


def draft_rejected(
    *,
    organization_id: uuid.UUID,
    draft_id: uuid.UUID,
    user_id: uuid.UUID,
    feedback_event_id: uuid.UUID,
    category: str,
    reason: str,
    correlation_id: str,
    review_session_id: uuid.UUID | None = None,
    reason_codes: list[str] | None = None,
) -> DomainEvent:
    payload: dict[str, Any] = {
        "draft_id": str(draft_id),
        "user_id": str(user_id),
        "feedback_event_id": str(feedback_event_id),
        "category": category,
        "reason": reason,
    }
    if review_session_id is not None:
        payload["review_session_id"] = str(review_session_id)
    if reason_codes:
        payload["reason_codes"] = list(reason_codes)
    return DomainEvent(
        event_type="DraftRejected",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload=payload,
    )


def draft_edited(
    *,
    organization_id: uuid.UUID,
    draft_id: uuid.UUID,
    user_id: uuid.UUID,
    feedback_event_id: uuid.UUID,
    original_text: str,
    edited_text: str,
    correlation_id: str,
    review_session_id: uuid.UUID | None = None,
    version_refs: list[dict[str, Any]] | None = None,
) -> DomainEvent:
    payload: dict[str, Any] = {
        "draft_id": str(draft_id),
        "user_id": str(user_id),
        "feedback_event_id": str(feedback_event_id),
        "original_text": original_text,
        "edited_text": edited_text,
    }
    if review_session_id is not None:
        payload["review_session_id"] = str(review_session_id)
    if version_refs:
        payload["version_refs"] = list(version_refs)
    return DomainEvent(
        event_type="DraftEdited",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload=payload,
    )


def image_generated(
    *,
    organization_id: uuid.UUID,
    draft_id: uuid.UUID,
    job_id: uuid.UUID,
    storage_key: str,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="ImageGenerated",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={
            "draft_id": str(draft_id),
            "job_id": str(job_id),
            "storage_key": storage_key,
        },
    )


def carousel_generated(
    *,
    organization_id: uuid.UUID,
    draft_id: uuid.UUID,
    deck_id: uuid.UUID,
    slide_count: int,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="CarouselGenerated",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={
            "draft_id": str(draft_id),
            "deck_id": str(deck_id),
            "slide_count": slide_count,
        },
    )


def article_imported(
    *,
    organization_id: uuid.UUID,
    article_id: uuid.UUID,
    source_id: uuid.UUID | None,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="ArticleImported",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={
            "article_id": str(article_id),
            "source_id": str(source_id) if source_id else None,
        },
    )


def prompt_evaluated(
    *,
    organization_id: uuid.UUID,
    prompt_name: str,
    version: str,
    outcome: str,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="PromptEvaluated",
        organization_id=organization_id,
        correlation_id=correlation_id,
        payload={
            "prompt_name": prompt_name,
            "version": version,
            "outcome": outcome,
        },
    )


def provider_failed(
    *,
    organization_id: uuid.UUID | None,
    provider: str,
    capability: str,
    error_message: str,
    correlation_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="ProviderFailed",
        organization_id=organization_id or uuid.UUID(int=0),
        correlation_id=correlation_id,
        payload={
            "provider": provider,
            "capability": capability,
            "error_message": error_message,
        },
    )
