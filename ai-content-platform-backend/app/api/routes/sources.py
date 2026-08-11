"""News source routes: list, create, run ingest."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.envelope import success_response
from app.api.schemas.news import CreateSourceRequest, UpdateSourceRequest
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.news.application.run_source import RunAllSourcesUseCase, RunSourceUseCase
from app.modules.news.application.use_cases import (
    CreateSourceUseCase,
    ListSourcesUseCase,
    UpdateSourceUseCase,
)
from app.modules.news.infrastructure.repositories import PgNewsSourceRepository
from app.infrastructure.connectors.newsdata import NEWSDATA_CATEGORIES

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
async def list_sources(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List all news sources for the current organization."""
    repo = PgNewsSourceRepository(session)
    use_case = ListSourcesUseCase(repo)
    sources = await use_case.execute(current_user.organization_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(sources, request_id=request_id)


@router.get("/newsdata/categories")
async def list_newsdata_categories(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Return selectable NewsData.io categories for the configure UI."""
    request_id = getattr(request.state, "request_id", "")
    return success_response(
        {
            "items": list(NEWSDATA_CATEGORIES),
            "max_selected": 5,
            "required": False,
            "note": "Optional. Leave empty to fetch latest news. Free plans max ~10 articles/request.",
        },
        request_id=request_id,
    )


@router.post("")
async def create_source(
    body: CreateSourceRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Create a new news source."""
    repo = PgNewsSourceRepository(session)
    use_case = CreateSourceUseCase(repo)
    source = await use_case.execute(
        org_id=current_user.organization_id,
        name=body.name,
        connector_type=body.connector_type,
        config_json=body.config_json,
        schedule_cron=body.schedule_cron,
        category=body.category,
        credibility_score=body.credibility_score,
        priority=body.priority,
        api_key_name=body.api_key_name,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(source, request_id=request_id)


@router.patch("/{source_id}")
async def update_source(
    source_id: uuid.UUID,
    body: UpdateSourceRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Update source name/config/schedule/enabled for custom fetching."""
    repo = PgNewsSourceRepository(session)
    use_case = UpdateSourceUseCase(repo)
    source = await use_case.execute(
        org_id=current_user.organization_id,
        source_id=source_id,
        name=body.name,
        config_json=body.config_json,
        schedule_cron=body.schedule_cron,
        enabled=body.enabled,
        category=body.category,
        credibility_score=body.credibility_score,
        priority=body.priority,
    )
    request_id = getattr(request.state, "request_id", "")
    return success_response(source, request_id=request_id)


@router.post("/sync-brand-policy")
async def sync_brand_news_policy(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Apply Brand Memory topics to GNews/Guardian/NewsData queries + relevance profile."""
    from app.modules.brand_intelligence.application.news_policy_service import (
        BrandNewsPolicyService,
    )

    data = await BrandNewsPolicyService(session).sync_news_sources(
        current_user.organization_id
    )
    await session.commit()
    request_id = getattr(request.state, "request_id", "")
    return success_response(data, request_id=request_id)


@router.post("/run-all")
async def run_all_sources(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ORJSONResponse:
    """Trigger ingest for every enabled source. Returns 202 with job list."""
    use_case = RunAllSourcesUseCase(session)
    result = await use_case.execute(org_id=current_user.organization_id)
    request_id = getattr(request.state, "request_id", "")
    return ORJSONResponse(
        status_code=202,
        content=success_response(result, request_id=request_id),
    )


@router.post("/{source_id}/run")
async def run_source(
    source_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ORJSONResponse:
    """Trigger an ingest run for a source. Returns 202 with job_id."""
    use_case = RunSourceUseCase(session)
    result = await use_case.execute(
        org_id=current_user.organization_id,
        source_id=source_id,
    )
    request_id = getattr(request.state, "request_id", "")
    return ORJSONResponse(
        status_code=202,
        content=success_response(result, request_id=request_id),
    )
