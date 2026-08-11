"""Review replay — reconstruct session history for audit."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.review.application.approval import ApprovalEngine
from app.modules.review.application.queue import InMemoryReviewQueue


class ReviewReplayService:
    def __init__(
        self,
        queue: InMemoryReviewQueue,
        approval: ApprovalEngine,
        history_log: list[dict[str, Any]] | None = None,
    ) -> None:
        self._queue = queue
        self._approval = approval
        self._history = history_log if history_log is not None else []

    def append(self, event: dict[str, Any]) -> None:
        self._history.append(dict(event))

    async def replay(self, session_id: uuid.UUID) -> dict[str, Any]:
        session = await self._queue.get(session_id)
        decisions = [d.to_dict() for d in self._approval.history(session_id)]
        comments = [c.to_dict() for c in self._approval.comments(session_id)]
        events = [e for e in self._history if e.get("session_id") == str(session_id)]
        return {
            "session": session.to_dict() if session else None,
            "decisions": decisions,
            "comments": comments,
            "events": events,
        }

    def list_history(self, session_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        if session_id is None:
            return list(self._history)
        sid = str(session_id)
        return [e for e in self._history if e.get("session_id") == sid]
