"""Approval engine — approve / reject / edit / partial / comment with history."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.review.application.feedback import FeedbackEngine
from app.modules.review.application.queue import InMemoryReviewQueue
from app.modules.review.application.versioning import VersioningService
from app.modules.review.domain.models import (
    DecisionType,
    ReviewComment,
    ReviewDecision,
    ReviewSession,
    ReviewStatus,
)


class ApprovalEngine:
    def __init__(
        self,
        queue: InMemoryReviewQueue | None = None,
        feedback: FeedbackEngine | None = None,
        versioning: VersioningService | None = None,
    ) -> None:
        self._queue = queue
        self._feedback = feedback or FeedbackEngine()
        self._versioning = versioning or VersioningService()
        self._decisions: dict[uuid.UUID, list[ReviewDecision]] = {}
        self._comments: dict[uuid.UUID, list[ReviewComment]] = {}

    async def approve(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        edited_text: str | None = None,
        reason_codes: list[str] | None = None,
        partial: bool = False,
        policy_snapshot: dict | None = None,
    ) -> ReviewDecision:
        if edited_text is not None:
            self._versioning.record(session, "edited", text=edited_text)
        status = ReviewStatus.PARTIAL_APPROVED if partial else ReviewStatus.APPROVED
        session.status = status
        self._versioning.record(
            session,
            "approved" if not partial else "partial_approved",
            text=edited_text,
        )
        decision = ReviewDecision(
            id=uuid.uuid4(),
            session_id=session.id,
            decision_type=DecisionType.PARTIAL_APPROVE if partial else DecisionType.APPROVE,
            actor_id=actor_id,
            reason_codes=tuple(reason_codes or ()),
            policy_snapshot=dict(policy_snapshot or {}),
            created_at=datetime.now(timezone.utc),
        )
        self._decisions.setdefault(session.id, []).append(decision)
        if self._queue is not None:
            await self._queue.enqueue(session)
            await self._queue.update_status(session.id, str(status))
        return decision

    async def reject(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        reason: str,
        category: str,
        reason_codes: list[str] | None = None,
        policy_snapshot: dict | None = None,
    ) -> ReviewDecision:
        cat = self._feedback.normalize_category(category)
        codes = list(reason_codes or [])
        ok, errors = self._feedback.validate_reason_codes(codes, [cat])
        if not ok and codes:
            raise ValueError(";".join(errors))
        session.status = ReviewStatus.REJECTED
        decision = ReviewDecision(
            id=uuid.uuid4(),
            session_id=session.id,
            decision_type=DecisionType.REJECT,
            actor_id=actor_id,
            reason=reason,
            reason_codes=tuple(codes),
            categories=(cat,),
            policy_snapshot=dict(policy_snapshot or {}),
            created_at=datetime.now(timezone.utc),
        )
        self._decisions.setdefault(session.id, []).append(decision)
        if self._queue is not None:
            await self._queue.enqueue(session)
            await self._queue.update_status(session.id, str(ReviewStatus.REJECTED))
        return decision

    async def request_changes(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        reason: str,
        reason_codes: list[str] | None = None,
        policy_snapshot: dict | None = None,
    ) -> ReviewDecision:
        session.status = ReviewStatus.NEEDS_CHANGES
        decision = ReviewDecision(
            id=uuid.uuid4(),
            session_id=session.id,
            decision_type=DecisionType.NEEDS_CHANGES,
            actor_id=actor_id,
            reason=reason,
            reason_codes=tuple(reason_codes or ()),
            policy_snapshot=dict(policy_snapshot or {}),
            created_at=datetime.now(timezone.utc),
        )
        self._decisions.setdefault(session.id, []).append(decision)
        if self._queue is not None:
            await self._queue.enqueue(session)
            await self._queue.update_status(session.id, str(ReviewStatus.NEEDS_CHANGES))
        return decision

    async def record_edit(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        original: str,
        edited: str,
        policy_snapshot: dict | None = None,
    ) -> tuple[ReviewDecision, dict]:
        diff = self._versioning.diff(original, edited)
        self._versioning.record(session, "edited", text=edited)
        if session.status == ReviewStatus.PENDING:
            session.status = ReviewStatus.IN_REVIEW
        decision = ReviewDecision(
            id=uuid.uuid4(),
            session_id=session.id,
            decision_type=DecisionType.EDIT,
            actor_id=actor_id,
            reason=f"edit_distance={diff['edit_distance']}",
            policy_snapshot={**(policy_snapshot or {}), "diff": diff},
            created_at=datetime.now(timezone.utc),
        )
        self._decisions.setdefault(session.id, []).append(decision)
        if self._queue is not None:
            await self._queue.enqueue(session)
        return decision, diff

    async def add_comment(
        self,
        session_id: uuid.UUID,
        author_id: uuid.UUID,
        body: str,
        *,
        parent_id: uuid.UUID | None = None,
    ) -> ReviewComment:
        if not body.strip():
            raise ValueError("comment body cannot be empty")
        comment = ReviewComment(
            id=uuid.uuid4(),
            session_id=session_id,
            author_id=author_id,
            body=body.strip(),
            parent_id=parent_id,
            created_at=datetime.now(timezone.utc),
        )
        self._comments.setdefault(session_id, []).append(comment)
        if self._queue is not None:
            self._queue.bump_comments(session_id)
        return comment

    def history(self, session_id: uuid.UUID) -> list[ReviewDecision]:
        return list(self._decisions.get(session_id, []))

    def comments(self, session_id: uuid.UUID) -> list[ReviewComment]:
        return list(self._comments.get(session_id, []))
