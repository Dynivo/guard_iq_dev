"""Review workflow — approve/reject/edit/publish; learning via domain events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.observability import ensure_correlation_id
from app.infrastructure.events.factory import get_event_bus
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.learning import FeedbackEvent
from app.modules.review.application.engine import ReviewEngine
from app.modules.review.application.factory import ReviewFactory
from app.shared.events import EventBus, draft_approved, draft_edited, draft_rejected
from app.shared.events.session_context import reset_event_session, set_event_session
from app.shared.result import Failure, Result, Success, fail, ok


class ReviewService:
    """Persistence-facing review API. Does not import Learning (ADR 0029)."""

    def __init__(
        self,
        session: AsyncSession,
        event_bus: EventBus | None = None,
        engine: ReviewEngine | None = None,
    ) -> None:
        self._session = session
        self._bus = event_bus or get_event_bus()
        self._engine = engine or ReviewFactory.create_memory(event_bus=None)

    async def _publish(self, event) -> None:
        token = set_event_session(self._session)
        try:
            await self._bus.publish(event)
        finally:
            reset_event_session(token)

    async def _get_draft(self, org_id: uuid.UUID, draft_id: uuid.UUID) -> Draft:
        draft = await self._session.get(Draft, draft_id)
        if draft is None or draft.organization_id != org_id:
            raise NotFoundError("Draft", str(draft_id))
        return draft

    async def _ensure_session(
        self, org_id: uuid.UUID, draft: Draft
    ) -> uuid.UUID:
        """Find or create an in-memory review session for this draft."""
        items = await self._engine.queue.list_items(org_id)
        for item in items:
            if item.session.draft_id == draft.id:
                return item.session.id
        session = await self._engine.enqueue_draft(
            org_id,
            draft.id,
            content_type=draft.content_type or "linkedin_post",
            title=draft.hook,
            original_text=draft.generated_text,
        )
        return session.id

    async def approve(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        user_id: uuid.UUID,
        edited_text: str | None = None,
        scheduled_for: str | None = None,
        reason_codes: list[str] | None = None,
        partial: bool = False,
    ) -> Result[dict[str, Any]]:
        draft = await self._get_draft(org_id, draft_id)
        if edited_text is not None:
            draft.edited_text = edited_text
        draft.status = "partial_approved" if partial else "approved"
        meta = dict(draft.metadata_json or {})
        if scheduled_for:
            meta["scheduled_for"] = scheduled_for
        draft.metadata_json = meta
        event = FeedbackEvent(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=user_id,
            action="partial_approve" if partial else "approve",
            decision_note=None,
            reason_category=",".join(reason_codes) if reason_codes else None,
        )
        self._session.add(event)
        await self._session.flush()

        session_id = await self._ensure_session(org_id, draft)
        engine_result = await self._engine.approve(
            session_id,
            user_id,
            edited_text=edited_text,
            reason_codes=reason_codes,
            partial=partial,
            text=draft.edited_text or draft.generated_text or "",
            hook=draft.hook,
            feedback_event_id=event.id,
        )
        if isinstance(engine_result, Failure):
            # Policy denial after draft mutation — roll status back to pending_review path
            draft.status = "pending_review"
            return engine_result

        correlation_id = ensure_correlation_id()
        text = draft.edited_text or draft.generated_text or ""
        session = await self._engine.queue.get(session_id)
        version_refs = [v.to_dict() for v in session.version_refs] if session else None
        await self._publish(
            draft_approved(
                organization_id=org_id,
                draft_id=draft_id,
                user_id=user_id,
                feedback_event_id=event.id,
                content_type=draft.content_type or "linkedin_post",
                text=text,
                hook=draft.hook,
                correlation_id=correlation_id,
                review_session_id=session_id,
                reason_codes=reason_codes,
                version_refs=version_refs,
            )
        )
        return ok(
            {
                "id": str(draft.id),
                "status": draft.status,
                "review_session_id": str(session_id),
            }
        )

    async def reject(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
        category: str,
        reason_codes: list[str] | None = None,
    ) -> Result[dict[str, Any]]:
        if not reason.strip():
            return fail("EMPTY_REASON", "Rejection reason cannot be empty")
        draft = await self._get_draft(org_id, draft_id)
        draft.status = "rejected"
        event = FeedbackEvent(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=user_id,
            action="reject",
            reason_category=category,
            decision_note=reason,
        )
        self._session.add(event)
        await self._session.flush()

        session_id = await self._ensure_session(org_id, draft)
        engine_result = await self._engine.reject(
            session_id,
            user_id,
            reason=reason,
            category=category,
            reason_codes=reason_codes,
            feedback_event_id=event.id,
        )
        if isinstance(engine_result, Failure):
            draft.status = "pending_review"
            return engine_result

        correlation_id = ensure_correlation_id()
        await self._publish(
            draft_rejected(
                organization_id=org_id,
                draft_id=draft_id,
                user_id=user_id,
                feedback_event_id=event.id,
                category=category,
                reason=reason,
                correlation_id=correlation_id,
                review_session_id=session_id,
                reason_codes=reason_codes,
            )
        )
        return ok(
            {
                "id": str(draft.id),
                "status": draft.status,
                "review_session_id": str(session_id),
            }
        )

    async def edit(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        user_id: uuid.UUID,
        new_text: str,
    ) -> Result[dict[str, Any]]:
        if not new_text.strip():
            return fail("EMPTY_TEXT", "edited text cannot be empty")
        draft = await self._get_draft(org_id, draft_id)
        original = draft.generated_text or ""
        draft.edited_text = new_text
        event = FeedbackEvent(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=user_id,
            action="edit",
            diff_summary=f"len {len(original)} → {len(new_text)}",
        )
        self._session.add(event)
        await self._session.flush()

        session_id = await self._ensure_session(org_id, draft)
        await self._engine.edit(
            session_id,
            user_id,
            original_text=original,
            edited_text=new_text,
            feedback_event_id=event.id,
        )

        correlation_id = ensure_correlation_id()
        session = await self._engine.queue.get(session_id)
        version_refs = [v.to_dict() for v in session.version_refs] if session else None
        await self._publish(
            draft_edited(
                organization_id=org_id,
                draft_id=draft_id,
                user_id=user_id,
                feedback_event_id=event.id,
                original_text=original,
                edited_text=new_text,
                correlation_id=correlation_id,
                review_session_id=session_id,
                version_refs=version_refs,
            )
        )
        return ok(
            {
                "id": str(draft.id),
                "status": draft.status,
                "edited_text": draft.edited_text,
                "review_session_id": str(session_id),
            }
        )

    async def mark_published(
        self, org_id: uuid.UUID, draft_id: uuid.UUID
    ) -> Result[dict[str, Any]]:
        draft = await self._get_draft(org_id, draft_id)
        if draft.status not in {"approved", "published", "partial_approved"}:
            return fail(
                "INVALID_STATUS",
                "Only approved drafts can be marked published",
            )
        draft.status = "published"
        meta = dict(draft.metadata_json or {})
        meta["published_at"] = datetime.now(timezone.utc).isoformat()
        draft.metadata_json = meta
        items = await self._engine.queue.list_items(org_id)
        for item in items:
            if item.session.draft_id == draft_id:
                self._engine.versioning.record(item.session, "published")
                break
        return ok({"id": str(draft.id), "status": draft.status})

    async def list_queue(
        self,
        org_id: uuid.UUID,
        status: str = "pending",
        *,
        priority: str | None = None,
        assignee_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        # Prefer engine queue when populated; fall back to draft table for legacy statuses
        engine_items = await self._engine.queue.list_items(
            org_id, status=status if status not in {"pending_review"} else "pending",
            priority=priority,
            assignee_id=assignee_id,
        )
        if engine_items:
            return [i.to_dict() for i in engine_items]

        draft_status = status
        if status == "pending":
            draft_status = "pending_review"
        rows = (
            await self._session.execute(
                select(Draft)
                .where(Draft.organization_id == org_id, Draft.status == draft_status)
                .order_by(Draft.updated_at.desc())
            )
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "status": r.status,
                "hook": r.hook,
                "content_type": r.content_type,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    async def enqueue(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        priority: str = "normal",
        reviewer_ids: list[uuid.UUID] | None = None,
        template_id: str | None = None,
        topic: str | None = None,
        risk: str | None = None,
    ) -> Result[dict[str, Any]]:
        draft = await self._get_draft(org_id, draft_id)
        session = await self._engine.enqueue_draft(
            org_id,
            draft.id,
            content_type=draft.content_type or "linkedin_post",
            title=draft.hook,
            priority=priority,
            original_text=draft.generated_text,
            template_id=template_id,
            topic=topic,
            risk=risk,
        )
        if reviewer_ids:
            await self._engine.assign(session.id, reviewer_ids)
        session = await self._engine.queue.get(session.id)
        return ok(session.to_dict() if session else {"id": str(session.id)})

    async def session_history(self, session_id: uuid.UUID) -> list[dict[str, Any]]:
        return self._engine.history(session_id)

    async def add_comment(
        self,
        session_id: uuid.UUID,
        author_id: uuid.UUID,
        body: str,
        *,
        parent_id: uuid.UUID | None = None,
    ) -> Result[dict[str, Any]]:
        return await self._engine.comment(
            session_id, author_id, body, parent_id=parent_id
        )


def unwrap_result(result: Result[dict[str, Any]]) -> dict[str, Any]:
    """Map Result to value or raise ValidationError for API routes."""
    from app.core.exceptions import ValidationError

    if isinstance(result, Success):
        return result.value
    if isinstance(result, Failure):
        raise ValidationError(result.message)
    raise ValidationError("Unknown result")
