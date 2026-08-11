"""Assignment engine — multi-reviewer, escalate, ownership."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.review.domain.models import ReviewAssignment


class AssignmentEngine:
    def __init__(self, queue=None) -> None:
        self._assignments: dict[uuid.UUID, list[ReviewAssignment]] = {}
        self._queue = queue

    async def assign(
        self,
        session_id: uuid.UUID,
        reviewer_ids: list[uuid.UUID],
        *,
        role: str = "reviewer",
    ) -> list[ReviewAssignment]:
        now = datetime.now(timezone.utc)
        created: list[ReviewAssignment] = []
        existing = self._assignments.setdefault(session_id, [])
        known = {a.reviewer_id for a in existing}
        for rid in reviewer_ids:
            if rid in known:
                continue
            assignment = ReviewAssignment(
                id=uuid.uuid4(),
                session_id=session_id,
                reviewer_id=rid,
                role=role,
                status="assigned",
                assigned_at=now,
            )
            existing.append(assignment)
            created.append(assignment)
        if self._queue is not None:
            all_ids = [a.reviewer_id for a in existing]
            self._queue.set_assignees(session_id, all_ids)
        return created if created else list(existing)

    async def escalate(self, session_id: uuid.UUID, reviewer_id: uuid.UUID) -> ReviewAssignment:
        for a in self._assignments.get(session_id, []):
            if a.reviewer_id == reviewer_id:
                a.escalated = True
                a.status = "escalated"
                return a
        assignment = ReviewAssignment(
            id=uuid.uuid4(),
            session_id=session_id,
            reviewer_id=reviewer_id,
            role="escalation",
            status="escalated",
            escalated=True,
            assigned_at=datetime.now(timezone.utc),
        )
        self._assignments.setdefault(session_id, []).append(assignment)
        if self._queue is not None:
            self._queue.set_assignees(
                session_id, [a.reviewer_id for a in self._assignments[session_id]]
            )
        return assignment

    async def list_for_session(self, session_id: uuid.UUID) -> list[ReviewAssignment]:
        return list(self._assignments.get(session_id, []))
