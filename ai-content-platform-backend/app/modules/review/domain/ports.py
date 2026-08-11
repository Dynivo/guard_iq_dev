"""Review module ports — queue, assignment, approval, feedback, decision, versioning."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.modules.review.domain.models import (
    PolicyEvaluation,
    ReviewAssignment,
    ReviewComment,
    ReviewDecision,
    ReviewQueueItem,
    ReviewSession,
    ReviewVersionRef,
)


class ReviewQueuePort(Protocol):
    async def enqueue(self, session: ReviewSession) -> ReviewSession: ...

    async def get(self, session_id: uuid.UUID) -> ReviewSession | None: ...

    async def list_items(
        self,
        org_id: uuid.UUID,
        *,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: uuid.UUID | None = None,
    ) -> list[ReviewQueueItem]: ...

    async def update_status(self, session_id: uuid.UUID, status: str) -> ReviewSession: ...


class AssignmentEnginePort(Protocol):
    async def assign(
        self,
        session_id: uuid.UUID,
        reviewer_ids: list[uuid.UUID],
        *,
        role: str = "reviewer",
    ) -> list[ReviewAssignment]: ...

    async def escalate(self, session_id: uuid.UUID, reviewer_id: uuid.UUID) -> ReviewAssignment: ...

    async def list_for_session(self, session_id: uuid.UUID) -> list[ReviewAssignment]: ...


class FeedbackEnginePort(Protocol):
    def validate_reason_codes(
        self, codes: list[str], categories: list[str]
    ) -> tuple[bool, list[str]]: ...

    def normalize_category(self, category: str) -> str: ...


class ApprovalEnginePort(Protocol):
    async def approve(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        edited_text: str | None = None,
        reason_codes: list[str] | None = None,
        partial: bool = False,
    ) -> ReviewDecision: ...

    async def reject(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        reason: str,
        category: str,
        reason_codes: list[str] | None = None,
    ) -> ReviewDecision: ...

    async def request_changes(
        self,
        session: ReviewSession,
        actor_id: uuid.UUID,
        *,
        reason: str,
        reason_codes: list[str] | None = None,
    ) -> ReviewDecision: ...

    async def add_comment(
        self,
        session_id: uuid.UUID,
        author_id: uuid.UUID,
        body: str,
        *,
        parent_id: uuid.UUID | None = None,
    ) -> ReviewComment: ...


class DecisionEnginePort(Protocol):
    def evaluate(
        self,
        session: ReviewSession,
        *,
        decision_type: str,
        reviewer_count: int = 0,
        reason_codes: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> PolicyEvaluation: ...


class VersioningPort(Protocol):
    def record(
        self,
        session: ReviewSession,
        kind: str,
        *,
        text: str | None = None,
        version_id: str | None = None,
    ) -> ReviewSession: ...

    def diff(self, original: str, edited: str) -> dict[str, Any]: ...

    def rollback_ref(self, session: ReviewSession, kind: str) -> ReviewVersionRef | None: ...


class ReviewService(Protocol):
    """Legacy port for draft approve/reject/edit/publish (kept for compatibility)."""

    async def approve(self, org_id: uuid.UUID, draft_id: uuid.UUID, user_id: uuid.UUID) -> None: ...

    async def reject(
        self, org_id: uuid.UUID, draft_id: uuid.UUID, user_id: uuid.UUID, reason: str, category: str
    ) -> None: ...

    async def edit(
        self, org_id: uuid.UUID, draft_id: uuid.UUID, user_id: uuid.UUID, new_text: str
    ) -> None: ...

    async def mark_published(self, org_id: uuid.UUID, draft_id: uuid.UUID) -> None: ...
