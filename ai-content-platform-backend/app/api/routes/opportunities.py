"""Opportunity + Strategist briefing routes (Phase 1 Content Intelligence Workspace)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.exceptions import ValidationError
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.content.application.opportunity_composer import OpportunityComposerService

router = APIRouter(tags=["opportunities"])


class OpportunityDecisionBody(BaseModel):
    action: str = Field(..., description="save | ignore | clear")


@router.get("/opportunities")
async def list_opportunities(
    request: Request,
    limit: int = Query(30, ge=1, le=100),
    include_ignored: bool = Query(False),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Ranked Content Opportunities (business DTOs — not raw articles)."""
    svc = OpportunityComposerService(session)
    items = await svc.list_opportunities(
        current_user.organization_id,
        limit=limit,
        include_ignored=include_ignored,
    )
    return success_response(
        {"items": items, "total": len(items), "estimates_label": "estimated"},
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/opportunities/summary")
async def opportunities_summary(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Daily Briefing counters."""
    svc = OpportunityComposerService(session)
    data = await svc.summary(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/strategist/briefing")
async def strategist_briefing(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """AI Strategist Copilot narrative + recommended action + memory."""
    svc = OpportunityComposerService(session)
    data = await svc.strategist_briefing(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/opportunities/{opportunity_id}/decision")
async def opportunity_decision(
    opportunity_id: str,
    body: OpportunityDecisionBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Save for later / ignore (stored on brand kit preferences until Opportunity entity lands)."""
    svc = OpportunityComposerService(session)
    try:
        result = await svc.set_decision(
            current_user.organization_id,
            opportunity_id,
            body.action.strip().lower(),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return success_response(result, request_id=getattr(request.state, "request_id", ""))
