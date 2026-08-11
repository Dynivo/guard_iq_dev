"""Article routes: list, categories, trends, get by ID."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.envelope import success_response
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.news.application.use_cases import (
    GetArticleUseCase,
    ListArticleCategoriesUseCase,
    ListArticlesUseCase,
)
from app.modules.news.infrastructure.enrichment_store import list_org_trends
from app.modules.news.infrastructure.repositories import PgArticleRepository

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
async def list_articles(
    request: Request,
    status: str | None = Query(None, description="Filter by article status"),
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List articles for the current organization, with optional filters."""
    repo = PgArticleRepository(session)
    use_case = ListArticlesUseCase(repo)
    result = await use_case.execute(
        org_id=current_user.organization_id,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.get("/categories")
async def list_article_categories(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List distinct article categories with counts for the org."""
    repo = PgArticleRepository(session)
    use_case = ListArticleCategoriesUseCase(repo)
    result = await use_case.execute(org_id=current_user.organization_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(result, request_id=request_id)


@router.get("/trends")
async def list_article_trends(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List durable topic trends for the current organization."""
    items = await list_org_trends(
        session, current_user.organization_id, limit=limit
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(
        {"items": items, "total": len(items)}, request_id=request_id
    )


@router.get("/{article_id}")
async def get_article(
    article_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Get a single article by ID."""
    repo = PgArticleRepository(session)
    use_case = GetArticleUseCase(repo)
    article = await use_case.execute(
        org_id=current_user.organization_id,
        article_id=article_id,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(article, request_id=request_id)
