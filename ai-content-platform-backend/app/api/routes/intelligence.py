"""Intelligence routes: rescore + admin relevance override."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.intelligence.application.relevance_override import (
    SetArticleRelevanceUseCase,
)
from app.modules.intelligence.application.screening_batches import (
    StartScreeningBatchUseCase,
    get_screening_status,
    schedule_screening_batch,
)
from app.modules.intelligence.application.workflow import IntelligenceWorkflow

router = APIRouter(prefix="/articles", tags=["intelligence"])


class RelevanceOverrideBody(BaseModel):
    status: str = Field(
        ...,
        description="relevant | irrelevant | scored",
    )
    note: str | None = Field(default=None, max_length=1000)


@router.post("/rescore-new")
async def rescore_new_articles(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Run the next user-commanded batch of up to 100 unscored articles."""
    org_id = current_user.organization_id
    result = await StartScreeningBatchUseCase(session).execute(
        org_id, mode="unscored"
    )
    # Persist the Job and article `screening` claims before its task opens
    # independent sessions. This is also the duplicate-click boundary.
    await session.commit()
    from app.infrastructure.postgres.session import async_session_factory

    if result.get("queued") and result.get("job_id"):
        schedule_screening_batch(uuid.UUID(result["job_id"]), async_session_factory)

    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.post("/rescore-relevant")
async def rescore_relevant_articles(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Explicitly rescore up to 100 least-recently scored relevant articles."""
    org_id = current_user.organization_id
    result = await StartScreeningBatchUseCase(session).execute(
        org_id, mode="relevant"
    )
    await session.commit()
    from app.infrastructure.postgres.session import async_session_factory

    if result.get("queued") and result.get("job_id"):
        schedule_screening_batch(uuid.UUID(result["job_id"]), async_session_factory)
    return success_response(
        result, request_id=getattr(request.state, "request_id", "")
    )


@router.get("/screening-status")
async def screening_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Return queue depth and durable progress for the active/latest batch."""
    result = await get_screening_status(session, current_user.organization_id)
    return success_response(
        result, request_id=getattr(request.state, "request_id", "")
    )


@router.patch("/{article_id}/relevance")
async def override_article_relevance(
    article_id: uuid.UUID,
    body: RelevanceOverrideBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Admin/editor override of relevance; records a learning preference/rule."""
    result = await SetArticleRelevanceUseCase(session).execute(
        org_id=current_user.organization_id,
        article_id=article_id,
        user_id=current_user.user_id,
        role=str(current_user.role),
        status=body.status,
        note=body.note,
    )
    return success_response(
        result, request_id=getattr(request.state, "request_id", "")
    )


@router.post("/{article_id}/rescore")
async def rescore_article(
    article_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Run the intelligence workflow (embed + score) for an article."""
    workflow = IntelligenceWorkflow(session, AIOrchestratorFactory.create())
    result = await workflow.run(
        org_id=current_user.organization_id,
        article_id=article_id,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)
