"""In-memory review queue — filter by status, priority, assignee."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.review.domain.models import ReviewQueueItem, ReviewSession, ReviewStatus


class InMemoryReviewQueue:
    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, ReviewSession] = {}
        self._assignees: dict[uuid.UUID, list[uuid.UUID]] = {}
        self._comment_counts: dict[uuid.UUID, int] = {}

    async def enqueue(self, session: ReviewSession) -> ReviewSession:
        now = datetime.now(timezone.utc)
        if session.created_at is None:
            session.created_at = now
        session.updated_at = now
        self._sessions[session.id] = session
        self._assignees.setdefault(session.id, [])
        self._comment_counts.setdefault(session.id, 0)
        return session

    async def get(self, session_id: uuid.UUID) -> ReviewSession | None:
        return self._sessions.get(session_id)

    async def list_items(
        self,
        org_id: uuid.UUID,
        *,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: uuid.UUID | None = None,
    ) -> list[ReviewQueueItem]:
        items: list[ReviewQueueItem] = []
        for sid, session in self._sessions.items():
            if session.organization_id != org_id:
                continue
            if status and str(session.status) != status:
                continue
            if priority and str(session.priority) != priority:
                continue
            assignees = tuple(self._assignees.get(sid, []))
            if assignee_id is not None and assignee_id not in assignees:
                continue
            items.append(
                ReviewQueueItem(
                    session=session,
                    assignee_ids=assignees,
                    comment_count=self._comment_counts.get(sid, 0),
                )
            )
        items.sort(
            key=lambda i: (
                -(i.session.updated_at.timestamp() if i.session.updated_at else 0),
            )
        )
        return items

    async def update_status(self, session_id: uuid.UUID, status: str) -> ReviewSession:
        session = self._sessions[session_id]
        session.status = ReviewStatus(status)
        session.updated_at = datetime.now(timezone.utc)
        self._sessions[session_id] = session
        return session

    def set_assignees(self, session_id: uuid.UUID, reviewer_ids: list[uuid.UUID]) -> None:
        self._assignees[session_id] = list(reviewer_ids)

    def bump_comments(self, session_id: uuid.UUID) -> None:
        self._comment_counts[session_id] = self._comment_counts.get(session_id, 0) + 1
