"""Review and publishing queue routes — RBAC enforced."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.review.application.replay import ReviewReplayService
from app.modules.review.application.service import ReviewService, unwrap_result

router = APIRouter(tags=["review"])


class RejectBody(BaseModel):
    reason: str = Field(min_length=1)
    category: str = Field(default="tone")
    reason_codes: list[str] = Field(default_factory=list)


class ApproveBody(BaseModel):
    edited_text: str | None = None
    scheduled_for: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    partial: bool = False


class EditBody(BaseModel):
    edited_text: str = Field(min_length=1)


class EnqueueBody(BaseModel):
    draft_id: uuid.UUID
    priority: str = "normal"
    reviewer_ids: list[uuid.UUID] = Field(default_factory=list)
    template_id: str | None = None
    topic: str | None = None
    risk: str | None = None


class AssignBody(BaseModel):
    reviewer_ids: list[uuid.UUID] = Field(min_length=1)
    role: str = "reviewer"


class CommentBody(BaseModel):
    body: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None


@router.get("/queue")
async def get_queue(
    request: Request,
    status: str = Query(default="pending"),
    priority: str | None = Query(default=None),
    assignee_id: uuid.UUID | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    data = await svc.list_queue(
        current_user.organization_id,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/queue")
async def enqueue_review(
    body: EnqueueBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(
        await svc.enqueue(
            current_user.organization_id,
            body.draft_id,
            priority=body.priority,
            reviewer_ids=body.reviewer_ids or None,
            template_id=body.template_id,
            topic=body.topic,
            risk=body.risk,
        )
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/sessions/{session_id}/assign")
async def assign_reviewers(
    session_id: uuid.UUID,
    body: AssignBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(
        await svc._engine.assign(session_id, body.reviewer_ids, role=body.role)
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/sessions/{session_id}/comments")
async def add_comment(
    session_id: uuid.UUID,
    body: CommentBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(
        await svc.add_comment(
            session_id,
            current_user.user_id,
            body.body,
            parent_id=body.parent_id,
        )
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.get("/sessions/{session_id}/history")
async def session_history(
    session_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    data = await svc.session_history(session_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/sessions/{session_id}/replay")
async def session_replay(
    session_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    replay = ReviewReplayService(svc._engine.queue, svc._engine.approval, svc._engine._history)
    data = await replay.replay(session_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: uuid.UUID,
    body: ApproveBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(
        await svc.approve(
            current_user.organization_id,
            draft_id,
            current_user.user_id,
            edited_text=body.edited_text,
            scheduled_for=body.scheduled_for,
            reason_codes=body.reason_codes or None,
            partial=body.partial,
        )
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: uuid.UUID,
    body: RejectBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(
        await svc.reject(
            current_user.organization_id,
            draft_id,
            current_user.user_id,
            reason=body.reason,
            category=body.category,
            reason_codes=body.reason_codes or None,
        )
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/drafts/{draft_id}/edit")
async def edit_draft(
    draft_id: uuid.UUID,
    body: EditBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(
        await svc.edit(
            current_user.organization_id,
            draft_id,
            current_user.user_id,
            new_text=body.edited_text,
        )
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/drafts/{draft_id}/published")
async def mark_published(
    draft_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    result = unwrap_result(await svc.mark_published(current_user.organization_id, draft_id))
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.get("/reviewers/{reviewer_id}/profile")
async def get_reviewer_profile(
    reviewer_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    profile = svc._engine.reviewer_intelligence.get(
        current_user.organization_id, reviewer_id
    )
    data = profile.to_dict() if profile else {
        "reviewer_id": str(reviewer_id),
        "organization_id": str(current_user.organization_id),
        "review_accuracy": 0.0,
        "average_edit_distance": 0.0,
        "approval_rate": 0.0,
        "rejection_rate": 0.0,
        "specializations": [],
        "recommendation_score": 0.0,
    }
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/workflow-templates")
async def list_workflow_templates(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    svc = ReviewService(session)
    ids = svc._engine.workflow_templates.list_ids()
    return success_response(
        {"templates": ids},
        request_id=getattr(request.state, "request_id", ""),
    )
