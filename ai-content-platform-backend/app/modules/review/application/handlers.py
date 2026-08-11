"""Workflow handlers for Review Engine."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.review.application.factory import ReviewFactory
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode
from app.shared.result import Failure


def _engine_from_context(context: WorkflowContext):
    engine = context.get("_review_engine")
    if engine is None:
        engine = ReviewFactory.create_memory()
        context.set("_review_engine", engine)
    return engine


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class ReviewQueueHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        org_id = _uuid(context.get("organization_id") or uuid.uuid4())
        draft_id = _uuid(context.get("draft_id") or uuid.uuid4())
        session = await engine.enqueue_draft(
            org_id,
            draft_id,
            content_type=str(context.get("content_type") or "linkedin_post"),
            title=context.get("title") or context.get("hook"),
            priority=str(context.get("priority") or "normal"),
            original_text=context.get("text") or context.get("original_text"),
            template_id=context.get("template_id") or node.config.get("template_id"),
            topic=context.get("topic") or node.config.get("topic"),
            risk=context.get("risk") or node.config.get("risk"),
        )
        payload = {"review.session": session.to_dict(), "review_session_id": str(session.id)}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ReviewAssignHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        session_id = _uuid(context.get("review_session_id") or (context.get("review.session") or {}).get("id"))
        reviewers_raw = context.get("reviewer_ids") or node.config.get("reviewer_ids") or []
        reviewer_ids = [_uuid(r) for r in reviewers_raw] or [uuid.uuid4()]
        result = await engine.assign(session_id, reviewer_ids)
        if isinstance(result, Failure):
            return NodeOutcome(success=False, error_message=result.message)
        payload = {"review.assignments": result.value.get("assignments")}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ReviewApproveHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        session_id = _uuid(context.get("review_session_id") or (context.get("review.session") or {}).get("id"))
        actor_id = _uuid(context.get("actor_id") or context.get("user_id") or uuid.uuid4())
        result = await engine.approve(
            session_id,
            actor_id,
            edited_text=context.get("edited_text"),
            reason_codes=list(context.get("reason_codes") or []),
            partial=bool(context.get("partial") or node.config.get("partial")),
            text=str(context.get("text") or ""),
            hook=context.get("hook"),
        )
        if isinstance(result, Failure):
            return NodeOutcome(success=False, error_message=result.message)
        payload = {"review.decision": result.value.get("decision"), "review.approved": True}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ReviewRejectHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        session_id = _uuid(context.get("review_session_id") or (context.get("review.session") or {}).get("id"))
        actor_id = _uuid(context.get("actor_id") or context.get("user_id") or uuid.uuid4())
        result = await engine.reject(
            session_id,
            actor_id,
            reason=str(context.get("reason") or node.config.get("reason") or "Rejected"),
            category=str(context.get("category") or "general"),
            reason_codes=list(context.get("reason_codes") or []),
        )
        if isinstance(result, Failure):
            return NodeOutcome(success=False, error_message=result.message)
        payload = {"review.decision": result.value.get("decision"), "review.rejected": True}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ReviewEditHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        session_id = _uuid(context.get("review_session_id") or (context.get("review.session") or {}).get("id"))
        actor_id = _uuid(context.get("actor_id") or context.get("user_id") or uuid.uuid4())
        result = await engine.edit(
            session_id,
            actor_id,
            original_text=str(context.get("original_text") or context.get("text") or ""),
            edited_text=str(context.get("edited_text") or ""),
        )
        if isinstance(result, Failure):
            return NodeOutcome(success=False, error_message=result.message)
        payload = {
            "review.decision": result.value.get("decision"),
            "review.diff": result.value.get("diff"),
            "review.edited": True,
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


def register_review_handlers(node_registry) -> None:
    node_registry.register("review.queue", ReviewQueueHandler())
    node_registry.register("review.assign", ReviewAssignHandler())
    node_registry.register("review.approve", ReviewApproveHandler())
    node_registry.register("review.reject", ReviewRejectHandler())
    node_registry.register("review.edit", ReviewEditHandler())
