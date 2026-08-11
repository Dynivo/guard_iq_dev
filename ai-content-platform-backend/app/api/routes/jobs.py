"""Jobs listing routes — use cases only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.jobs.application.use_cases import GetJobUseCase, ListJobsUseCase

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await ListJobsUseCase(session).execute(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await GetJobUseCase(session).execute(current_user.organization_id, job_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))
