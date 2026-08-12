"""Draft routes: generate, list, get, update — with RBAC and org scoping."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.draft import (
    GenerateDraftRequest,
    RegenerateDraftRequest,
    UpdateDraftRequest,
)
from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.content.application.use_cases import (
    DeleteDraftUseCase,
    GenerateDraftUseCase,
    GetDraftUseCase,
    ListDraftsUseCase,
    ListDraftVersionsUseCase,
    RegenerateDraftSectionUseCase,
    UpdateDraftUseCase,
)

router = APIRouter(tags=["content"])


@router.post("/articles/{article_id}/generate-draft", status_code=201)
async def generate_draft(
    article_id: uuid.UUID,
    body: GenerateDraftRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Generate a content draft from a scored article."""
    use_case = GenerateDraftUseCase(session, AIOrchestratorFactory.create())
    result = await use_case.execute(
        org_id=current_user.organization_id,
        article_id=article_id,
        content_type=body.content_type,
        force=body.force,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.get("/drafts")
async def list_drafts(
    request: Request,
    status: str | None = Query(default=None, description="Filter by draft status"),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List all drafts for the current organization."""
    use_case = ListDraftsUseCase(session)
    result = await use_case.execute(current_user.organization_id, status=status)
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.get("/drafts/{draft_id}")
async def get_draft(
    draft_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Get a single draft with variations (org-scoped)."""
    use_case = GetDraftUseCase(session)
    result = await use_case.execute(current_user.organization_id, draft_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.patch("/drafts/{draft_id}")
async def update_draft(
    draft_id: uuid.UUID,
    body: UpdateDraftRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Update a draft (edited_text only)."""
    use_case = UpdateDraftUseCase(session)
    result = await use_case.execute(
        current_user.organization_id, draft_id, edited_text=body.edited_text
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.delete("/drafts/{draft_id}")
async def delete_draft(
    draft_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Permanently delete a draft (org-scoped)."""
    use_case = DeleteDraftUseCase(session)
    result = await use_case.execute(current_user.organization_id, draft_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.post("/drafts/{draft_id}/regenerate")
async def regenerate_draft_section(
    draft_id: uuid.UUID,
    body: RegenerateDraftRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Regenerate the full post (default) or a section. Optional guidance. Returns previous vs new."""
    use_case = RegenerateDraftSectionUseCase(session, AIOrchestratorFactory.create())
    result = await use_case.execute(
        current_user.organization_id,
        draft_id,
        section=body.section or "full",
        guidance=body.guidance,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.get("/drafts/{draft_id}/versions")
async def list_draft_versions(
    draft_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List previous versions for before/after comparison."""
    result = await ListDraftVersionsUseCase(session).execute(
        current_user.organization_id, draft_id
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)
