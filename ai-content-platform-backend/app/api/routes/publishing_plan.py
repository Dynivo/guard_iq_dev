"""Publishing Plan routes — mix status, fill educational, regenerate plan."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.exceptions import ValidationError
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.content.application.calendar_view import CalendarViewService
from app.modules.content.application.publishing_plan import PublishingPlanService
from app.modules.content.application.use_cases import GenerateDraftUseCase

router = APIRouter(prefix="/publishing-plan", tags=["publishing-plan"])


class RegeneratePlanBody(BaseModel):
    max_generate: int | None = Field(
        default=None,
        ge=1,
        le=15,
        description="Optional cap on total drafts generated this call",
    )


class SeedCalendarBody(BaseModel):
    rebalance: bool = Field(
        default=False,
        description="If true, re-place drafts whose dates fall outside the plan window",
    )


@router.get("")
async def get_publishing_plan(
    request: Request,
    include_ideas: bool = Query(True, description="Include educational idea candidates"),
    ideas_limit: int = Query(15, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Brand window mix progress, workday slots, review queue, optional ideas."""
    svc = PublishingPlanService(session)
    plan = await svc.get_plan(current_user.organization_id)
    if include_ideas:
        plan["ideas"] = await svc.list_educational_ideas(
            current_user.organization_id, limit=ideas_limit
        )
    return success_response(
        plan,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/fill-educational")
async def fill_educational(
    request: Request,
    max_generate: int | None = Query(
        None,
        ge=1,
        le=10,
        description="Cap how many drafts to generate this call (default = full gap)",
    ),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Generate educational drafts from unused relevant articles until gap filled."""
    generate_uc = GenerateDraftUseCase(session)
    svc = PublishingPlanService(session, generate_uc=generate_uc)
    result = await svc.fill_educational(
        current_user.organization_id,
        max_generate=max_generate,
        ensure_image=True,
    )
    plan = await svc.get_plan(current_user.organization_id)
    result["plan"] = {
        "counts": plan["counts"],
        "gaps": plan["gaps"],
        "total_count": plan["total_count"],
        "target": plan["target"],
        "window": plan["window"],
        "slots": plan["slots"],
        "needs_capture": plan.get("needs_capture"),
    }
    return success_response(
        result,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/regenerate")
async def regenerate_plan(
    request: Request,
    body: RegeneratePlanBody | None = None,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Rebuild mix: fill educational + Capture gaps with LinkedIn copy + image."""
    generate_uc = GenerateDraftUseCase(session)
    svc = PublishingPlanService(session, generate_uc=generate_uc)
    result = await svc.regenerate_plan(
        current_user.organization_id,
        max_generate=(body.max_generate if body else None),
    )
    return success_response(
        result,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/seed-calendar")
async def seed_publishing_calendar(
    request: Request,
    body: SeedCalendarBody | None = None,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Assign drafts onto plan workdays so the monthly calendar is labeled."""
    svc = PublishingPlanService(session)
    result = await svc.seed_calendar(
        current_user.organization_id,
        rebalance=bool(body.rebalance) if body else False,
    )
    cal = await CalendarViewService(session).month_view(current_user.organization_id)
    result["calendar"] = {
        "month_label": cal.get("month_label"),
        "events": cal.get("events"),
        "unscheduled_count": len(cal.get("unscheduled") or []),
    }
    return success_response(
        result,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/clear-calendar")
async def clear_publishing_calendar(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Unschedule every plan-origin draft. Drafts stay in Drafts, just no calendar date."""
    svc = PublishingPlanService(session)
    result = await svc.clear_calendar(current_user.organization_id)
    return success_response(
        result,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/calendar")
async def get_publishing_calendar(
    request: Request,
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Google-style monthly calendar: scheduled posts + plan slot suggestions."""
    today = date.today()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    try:
        view = await CalendarViewService(session).month_view(
            current_user.organization_id,
            year=y,
            month=m,
            today=today,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return success_response(
        view,
        request_id=getattr(request.state, "request_id", ""),
    )
