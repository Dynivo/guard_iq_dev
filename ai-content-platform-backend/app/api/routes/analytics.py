"""Observability API routes — live DB metrics, traces, evaluations, health, cost."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.api.schemas.analytics import ProviderBudgetUpdateRequest
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.analytics.application.runtime import get_observability_engine
from app.modules.analytics.application.service import AnalyticsService
from app.modules.ai.application.provider_budgets import ProviderBudgetService
from app.modules.auth.domain.entities import AuthenticatedUser

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_service(
    session: AsyncSession = Depends(get_async_session),
) -> AnalyticsService:
    return AnalyticsService(get_observability_engine(), session=session)


@router.get("/metrics")
async def get_metrics(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = await svc.metrics_live(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/traces")
async def get_traces(
    request: Request,
    correlation_id: str | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = svc.traces(current_user.organization_id, correlation_id=correlation_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/evaluations")
async def get_evaluations(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return success_response(
        svc.evaluations(current_user.organization_id),
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/providers/health")
async def provider_health(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = await svc.provider_health(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/models/health")
async def model_health(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = await svc.model_health(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/workflows/health")
async def workflow_health(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = await svc.workflow_health(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/cost")
async def get_cost(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = await svc.cost(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/usage")
async def get_usage(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    data = await svc.usage(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/provider-budgets")
async def get_provider_budgets(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> dict:
    data = await ProviderBudgetService().list_for_org(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.put("/provider-budgets")
async def update_provider_budget(
    body: ProviderBudgetUpdateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.OWNER)),
) -> dict:
    data = await ProviderBudgetService().update_limit(
        current_user.organization_id,
        provider=body.provider,
        monthly_limit_usd=body.monthly_limit_usd,
        is_enabled=body.is_enabled,
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/correlation/{correlation_id}")
async def correlation_explorer(
    correlation_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return success_response(
        svc.correlation(current_user.organization_id, correlation_id),
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/replay/{correlation_id}")
async def replay_traces(
    correlation_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return success_response(
        svc.replay(current_user.organization_id, correlation_id),
        request_id=getattr(request.state, "request_id", ""),
    )
