"""Workflow handlers for Learning Engine (subscriber-side nodes)."""

from __future__ import annotations

from typing import Any

from app.modules.learning.application.factory import LearningFactory
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode
from app.shared.events.types import DomainEvent, draft_approved, draft_edited, draft_rejected
import uuid


def _engine_from_context(context: WorkflowContext):
    engine = context.get("_learning_engine")
    if engine is None:
        engine = LearningFactory.create_memory()
        context.set("_learning_engine", engine)
    return engine


def _event_from_context(context: WorkflowContext) -> DomainEvent | None:
    raw = context.get("domain_event")
    if isinstance(raw, DomainEvent):
        return raw
    event_type = str(context.get("event_type") or "")
    org_id = uuid.UUID(str(context.get("organization_id") or uuid.uuid4()))
    correlation_id = str(context.get("correlation_id") or "workflow-learning")
    draft_id = uuid.UUID(str(context.get("draft_id") or uuid.uuid4()))
    user_id = uuid.UUID(str(context.get("user_id") or uuid.uuid4()))
    feedback_id = uuid.UUID(str(context.get("feedback_event_id") or uuid.uuid4()))
    if event_type == "DraftApproved" or context.get("review.approved"):
        return draft_approved(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=user_id,
            feedback_event_id=feedback_id,
            content_type=str(context.get("content_type") or "linkedin_post"),
            text=str(context.get("text") or context.get("edited_text") or "Approved sample"),
            hook=context.get("hook"),
            correlation_id=correlation_id,
            review_session_id=(
                uuid.UUID(str(context.get("review_session_id")))
                if context.get("review_session_id")
                else None
            ),
        )
    if event_type == "DraftRejected" or context.get("review.rejected"):
        return draft_rejected(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=user_id,
            feedback_event_id=feedback_id,
            category=str(context.get("category") or "general"),
            reason=str(context.get("reason") or "Rejected"),
            correlation_id=correlation_id,
            review_session_id=(
                uuid.UUID(str(context.get("review_session_id")))
                if context.get("review_session_id")
                else None
            ),
        )
    if event_type == "DraftEdited" or context.get("review.edited"):
        return draft_edited(
            organization_id=org_id,
            draft_id=draft_id,
            user_id=user_id,
            feedback_event_id=feedback_id,
            original_text=str(context.get("original_text") or ""),
            edited_text=str(context.get("edited_text") or ""),
            correlation_id=correlation_id,
            review_session_id=(
                uuid.UUID(str(context.get("review_session_id")))
                if context.get("review_session_id")
                else None
            ),
        )
    return None


class LearningCaptureHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        event = _event_from_context(context)
        if event is None:
            return NodeOutcome(success=False, error_message="no domain event for learning.capture")
        le = engine.capture_event(event)
        if le is None:
            return NodeOutcome(success=False, error_message="event type not captured")
        payload = {"learning.event": le.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class LearningProcessHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        raw = context.get("learning.event")
        if not isinstance(raw, dict):
            return NodeOutcome(success=False, error_message="learning.event missing")
        from app.modules.learning.domain.models import LearningEvent
        from datetime import datetime

        le = LearningEvent(
            id=uuid.UUID(str(raw["id"])),
            organization_id=uuid.UUID(str(raw["organization_id"])),
            source_event_type=str(raw["source_event_type"]),
            correlation_id=str(raw["correlation_id"]),
            draft_id=uuid.UUID(str(raw["draft_id"])) if raw.get("draft_id") else None,
            review_session_id=(
                uuid.UUID(str(raw["review_session_id"])) if raw.get("review_session_id") else None
            ),
            feedback_event_id=(
                uuid.UUID(str(raw["feedback_event_id"])) if raw.get("feedback_event_id") else None
            ),
            payload=dict(raw.get("payload") or {}),
            captured_at=(
                datetime.fromisoformat(raw["captured_at"])
                if raw.get("captured_at")
                else None
            ),
        )
        artifacts = engine.process_event(le)
        payload = {"learning.artifacts": [a.to_dict() for a in artifacts]}
        context.update(payload)
        return NodeOutcome(success=True, outputs={"learning.artifact_count": len(artifacts)})


class LearningStoreHandler:
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        engine = _engine_from_context(context)
        raw_arts = context.get("learning.artifacts") or []
        from app.modules.learning.domain.models import (
            KnowledgeArtifact,
            KnowledgeLifecycle,
            LearningArtifactKind,
        )

        artifacts = []
        for r in raw_arts:
            if not isinstance(r, dict):
                continue
            artifacts.append(
                KnowledgeArtifact(
                    kind=LearningArtifactKind(str(r["kind"])),
                    organization_id=uuid.UUID(str(r["organization_id"])),
                    body=str(r["body"]),
                    category=str(r.get("category") or "general"),
                    metadata=dict(r.get("metadata") or {}),
                    confidence=float(r.get("confidence") or 0.5),
                    approval_count=int(r.get("approval_count") or 0),
                    usage_count=int(r.get("usage_count") or 0),
                    success_rate=float(r.get("success_rate") or 0.0),
                    created_from_review=bool(r.get("created_from_review", True)),
                    lifecycle=KnowledgeLifecycle(str(r.get("lifecycle") or "candidate")),
                    source_learning_event_id=(
                        uuid.UUID(str(r["source_learning_event_id"]))
                        if r.get("source_learning_event_id")
                        else None
                    ),
                    version=int(r.get("version") or 1),
                    supersedes_id=(
                        uuid.UUID(str(r["supersedes_id"])) if r.get("supersedes_id") else None
                    ),
                )
            )
        stored = await engine.store_artifacts(artifacts)
        status = engine.store.status()
        payload = {"learning.stored": stored, "learning.status": status}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


def register_learning_workflow_handlers(node_registry) -> None:
    node_registry.register("learning.capture", LearningCaptureHandler())
    node_registry.register("learning.process", LearningProcessHandler())
    node_registry.register("learning.store", LearningStoreHandler())
