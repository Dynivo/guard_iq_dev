"""Intelligence routes: rescore + admin relevance override."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.infrastructure.postgres.models.news import Article
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.intelligence.application.relevance_override import (
    SetArticleRelevanceUseCase,
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
    """Enqueue AI relevance for raw/scored articles (batch soft rescore)."""
    org_id = current_user.organization_id
    rows = (
        await session.execute(
            select(Article.id)
            .where(
                Article.organization_id == org_id,
                Article.status.in_(("raw", "scored", "normalized")),
            )
            .order_by(Article.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    ids = [str(r) for r in rows]

    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.intelligence.application.subscribers import _score_in_background

    for aid in ids:
        asyncio.create_task(
            _score_in_background(org_id, uuid.UUID(aid), async_session_factory),
            name=f"rescore-{aid}",
        )

    request_id = getattr(request.state, "request_id", "")
    return success_response(
        {"queued": len(ids), "article_ids": ids},
        request_id=request_id,
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
