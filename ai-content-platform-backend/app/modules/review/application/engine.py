"""ReviewEngine facade — queue → assign → decide → publish events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.observability import ensure_correlation_id
from app.modules.review.application.approval import ApprovalEngine
from app.modules.review.application.assignment import AssignmentEngine
from app.modules.review.application.cache import ReviewCache
from app.modules.review.application.decision import DecisionEngine
from app.modules.review.application.feedback import FeedbackEngine
from app.modules.review.application.metrics import InMemoryReviewMetrics
from app.modules.review.application.queue import InMemoryReviewQueue
from app.modules.review.application.reviewer_intelligence import ReviewerIntelligenceEngine
from app.modules.review.application.versioning import VersioningService
from app.modules.review.application.workflow_templates import ReviewWorkflowTemplateService
from app.modules.review.domain.models import (
    ReviewPriority,
    ReviewSession,
    ReviewStatus,
)
from app.shared.events import EventBus, draft_approved, draft_edited, draft_rejected
from app.shared.result import Result, fail, ok


class ReviewEngine:
    """Orchestrates human review without importing Learning (ADR 0029)."""

    def __init__(
        self,
        *,
        queue: InMemoryReviewQueue | None = None,
        assignment: AssignmentEngine | None = None,
        approval: ApprovalEngine | None = None,
        feedback: FeedbackEngine | None = None,
        decision: DecisionEngine | None = None,
        versioning: VersioningService | None = None,
        event_bus: EventBus | None = None,
        metrics: InMemoryReviewMetrics | None = None,
        cache: ReviewCache | None = None,
        history_log: list[dict[str, Any]] | None = None,
        config_dir: str | None = None,
        reviewer_intelligence: ReviewerIntelligenceEngine | None = None,
        workflow_templates: ReviewWorkflowTemplateService | None = None,
    ) -> None:
        self.queue = queue or InMemoryReviewQueue()
        self.assignment = assignment or AssignmentEngine(self.queue)
        self.feedback = feedback or FeedbackEngine(config_dir)
        self.decision = decision or DecisionEngine(config_dir)
        self.versioning = versioning or VersioningService()
        self.approval = approval or ApprovalEngine(
            self.queue, self.feedback, self.versioning
        )
        self._bus = event_bus
        self.metrics = metrics or InMemoryReviewMetrics()
        self.cache = cache or ReviewCache()
        self._history = history_log if history_log is not None else []
        self.reviewer_intelligence = reviewer_intelligence or ReviewerIntelligenceEngine(
            config_dir
        )
        self.workflow_templates = workflow_templates or ReviewWorkflowTemplateService(
            config_dir
        )

    def _log(self, kind: str, payload: dict[str, Any]) -> None:
        entry = {
            "kind": kind,
            "at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        self._history.append(entry)

    def _specs_from_session(self, session: ReviewSession) -> list[str]:
        raw = (session.metadata or {}).get("specializations") or []
        return [str(x) for x in raw]

    async def enqueue_draft(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        content_type: str = "linkedin_post",
        title: str | None = None,
        priority: str = "normal",
        original_text: str | None = None,
        due_date: datetime | None = None,
        template_id: str | None = None,
        topic: str | None = None,
        risk: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewSession:
        meta = dict(metadata or {})
        if topic:
            meta["topic"] = topic
        if risk:
            meta["risk"] = risk
        session = ReviewSession(
            id=uuid.uuid4(),
            organization_id=org_id,
            draft_id=draft_id,
            status=ReviewStatus.PENDING,
            priority=ReviewPriority(priority),
            content_type=content_type,
            title=title,
            due_date=due_date,
            metadata=meta,
        )
        if template_id:
            session = self.workflow_templates.apply(session, template_id)
        if original_text is not None:
            self.versioning.record(session, "original", text=original_text)
        await self.queue.enqueue(session)
        self.cache.invalidate(f"queue:{org_id}")
        self._log(
            "enqueue",
            {
                "session_id": str(session.id),
                "draft_id": str(draft_id),
                "template_id": template_id,
                "topic": session.metadata.get("topic"),
                "risk": session.metadata.get("risk"),
            },
        )
        items = await self.queue.list_items(org_id)
        self.metrics.set_queue_depth(len(items))
        return session

    async def assign(
        self,
        session_id: uuid.UUID,
        reviewer_ids: list[uuid.UUID],
        *,
        role: str = "reviewer",
    ) -> Result[dict[str, Any]]:
        session = await self.queue.get(session_id)
        if session is None:
            return fail("NOT_FOUND", f"session {session_id}")
        assignments = await self.assignment.assign(session_id, reviewer_ids, role=role)
        if session.status == ReviewStatus.PENDING:
            await self.queue.update_status(session_id, str(ReviewStatus.IN_REVIEW))
        self.metrics.record_assignment(len(assignments))
        self._log(
            "assign",
            {
                "session_id": str(session_id),
                "reviewers": [str(r) for r in reviewer_ids],
            },
        )
        return ok({"assignments": [a.to_dict() for a in assignments]})

    async def approve(
        self,
        session_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        edited_text: str | None = None,
        reason_codes: list[str] | None = None,
        partial: bool = False,
        text: str = "",
        hook: str | None = None,
        feedback_event_id: uuid.UUID | None = None,
    ) -> Result[dict[str, Any]]:
        session = await self.queue.get(session_id)
        if session is None:
            return fail("NOT_FOUND", f"session {session_id}")
        reviewers = await self.assignment.list_for_session(session_id)
        # Actual assignment count — do not floor at 1 when dynamic quorum > 1
        reviewer_count = len(reviewers) if reviewers else 0
        if reviewer_count == 0:
            # Solo approve allowed only when resolved quorum is 1
            resolved = self.decision.resolve_requirements(session)
            if int(resolved["quorum"]) <= 1:
                reviewer_count = 1
        evaluation = self.decision.evaluate(
            session,
            decision_type="partial_approve" if partial else "approve",
            reviewer_count=reviewer_count,
            reason_codes=reason_codes,
        )
        if not evaluation.allowed:
            return fail("POLICY_DENIED", ";".join(evaluation.reasons) or "policy denied")
        decision = await self.approval.approve(
            session,
            actor_id,
            edited_text=edited_text,
            reason_codes=reason_codes,
            partial=partial,
            policy_snapshot=evaluation.snapshot,
        )
        self.metrics.record_approval()
        self.reviewer_intelligence.record_approve(
            session.organization_id,
            actor_id,
            specializations=self._specs_from_session(session),
        )
        self._log(
            "approve",
            {"session_id": str(session_id), "decision_id": str(decision.id)},
        )
        if self._bus is not None:
            await self._bus.publish(
                draft_approved(
                    organization_id=session.organization_id,
                    draft_id=session.draft_id,
                    user_id=actor_id,
                    feedback_event_id=feedback_event_id or decision.id,
                    content_type=session.content_type,
                    text=edited_text or text,
                    hook=hook,
                    correlation_id=ensure_correlation_id(),
                    review_session_id=session.id,
                    reason_codes=reason_codes,
                    version_refs=[v.to_dict() for v in session.version_refs],
                )
            )
        return ok({"session": session.to_dict(), "decision": decision.to_dict()})

    async def reject(
        self,
        session_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        reason: str,
        category: str = "general",
        reason_codes: list[str] | None = None,
        feedback_event_id: uuid.UUID | None = None,
    ) -> Result[dict[str, Any]]:
        if not reason.strip():
            return fail("EMPTY_REASON", "Rejection reason cannot be empty")
        session = await self.queue.get(session_id)
        if session is None:
            return fail("NOT_FOUND", f"session {session_id}")
        cat = self.feedback.normalize_category(category)
        evaluation = self.decision.evaluate(
            session,
            decision_type="reject",
            reviewer_count=1,
            reason_codes=reason_codes,
            categories=[cat],
        )
        if not evaluation.allowed:
            return fail("POLICY_DENIED", ";".join(evaluation.reasons) or "policy denied")
        try:
            decision = await self.approval.reject(
                session,
                actor_id,
                reason=reason,
                category=cat,
                reason_codes=reason_codes,
                policy_snapshot=evaluation.snapshot,
            )
        except ValueError as exc:
            return fail("INVALID_FEEDBACK", str(exc))
        self.metrics.record_rejection()
        self.reviewer_intelligence.record_reject(
            session.organization_id,
            actor_id,
            specializations=self._specs_from_session(session),
        )
        self._log(
            "reject",
            {"session_id": str(session_id), "decision_id": str(decision.id)},
        )
        if self._bus is not None:
            await self._bus.publish(
                draft_rejected(
                    organization_id=session.organization_id,
                    draft_id=session.draft_id,
                    user_id=actor_id,
                    feedback_event_id=feedback_event_id or decision.id,
                    category=cat,
                    reason=reason,
                    correlation_id=ensure_correlation_id(),
                    review_session_id=session.id,
                    reason_codes=reason_codes,
                )
            )
        return ok({"session": session.to_dict(), "decision": decision.to_dict()})

    async def edit(
        self,
        session_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        original_text: str,
        edited_text: str,
        feedback_event_id: uuid.UUID | None = None,
    ) -> Result[dict[str, Any]]:
        if not edited_text.strip():
            return fail("EMPTY_TEXT", "edited text cannot be empty")
        session = await self.queue.get(session_id)
        if session is None:
            return fail("NOT_FOUND", f"session {session_id}")
        evaluation = self.decision.evaluate(session, decision_type="edit", reviewer_count=1)
        decision, diff = await self.approval.record_edit(
            session,
            actor_id,
            original=original_text,
            edited=edited_text,
            policy_snapshot=evaluation.snapshot,
        )
        distance = int(diff.get("edit_distance") or 0)
        self.metrics.record_edit(edit_distance=distance)
        self.reviewer_intelligence.record_edit(
            session.organization_id, actor_id, edit_distance=float(distance)
        )
        self._log("edit", {"session_id": str(session_id), "diff": diff})
        if self._bus is not None:
            await self._bus.publish(
                draft_edited(
                    organization_id=session.organization_id,
                    draft_id=session.draft_id,
                    user_id=actor_id,
                    feedback_event_id=feedback_event_id or decision.id,
                    original_text=original_text,
                    edited_text=edited_text,
                    correlation_id=ensure_correlation_id(),
                    review_session_id=session.id,
                    version_refs=[v.to_dict() for v in session.version_refs],
                )
            )
        return ok(
            {
                "session": session.to_dict(),
                "decision": decision.to_dict(),
                "diff": diff,
            }
        )

    async def comment(
        self,
        session_id: uuid.UUID,
        author_id: uuid.UUID,
        body: str,
        *,
        parent_id: uuid.UUID | None = None,
    ) -> Result[dict[str, Any]]:
        try:
            comment = await self.approval.add_comment(
                session_id, author_id, body, parent_id=parent_id
            )
        except ValueError as exc:
            return fail("EMPTY_COMMENT", str(exc))
        self._log("comment", {"session_id": str(session_id), "comment_id": str(comment.id)})
        return ok(comment.to_dict())

    def history(self, session_id: uuid.UUID) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.approval.history(session_id)]
