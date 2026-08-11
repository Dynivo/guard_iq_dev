"""Organization routes: get org, list members."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.envelope import success_response
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.organization.application.use_cases import (
    GetOrganizationUseCase,
    ListMembersUseCase,
)
from app.modules.organization.infrastructure.repositories import PgOrganizationRepository

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/current")
async def get_current_organization(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Get the authenticated user's current organization."""
    repo = PgOrganizationRepository(session)
    use_case = GetOrganizationUseCase(repo)
    org = await use_case.execute(current_user.organization_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(org, request_id=request_id)


@router.get("/current/members")
async def list_members(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List all active members of the current organization."""
    repo = PgOrganizationRepository(session)
    use_case = ListMembersUseCase(repo)
    members = await use_case.execute(current_user.organization_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(members, request_id=request_id)
