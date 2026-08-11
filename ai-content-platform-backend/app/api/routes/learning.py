"""Learning center routes — use cases only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.learning.application.factory import LearningFactory
from app.modules.learning.application.use_cases import (
    GetLearningStatusUseCase,
    ListExamplesUseCase,
    ListPreferencesUseCase,
    ListRulesUseCase,
    UpdateExampleUseCase,
    UpdateRuleUseCase,
)

router = APIRouter(prefix="/learning", tags=["learning"])


class UpdateExampleBody(BaseModel):
    text: str | None = None
    hook: str | None = None
    weight: float | None = Field(default=None, ge=0, le=10)
    lifecycle: str | None = None
    is_active: bool | None = None


class UpdateRuleBody(BaseModel):
    text: str | None = None
    category: str | None = None
    priority: int | None = None
    lifecycle: str | None = None
    is_active: bool | None = None


@router.get("/examples")
async def list_examples(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await ListExamplesUseCase(session).execute(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.patch("/examples/{example_id}")
async def update_example(
    example_id: uuid.UUID,
    body: UpdateExampleBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await UpdateExampleUseCase(session).execute(
        current_user.organization_id,
        example_id,
        **body.model_dump(exclude_unset=True),
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/rules")
async def list_rules(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await ListRulesUseCase(session).execute(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    body: UpdateRuleBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await UpdateRuleUseCase(session).execute(
        current_user.organization_id,
        rule_id,
        **body.model_dump(exclude_unset=True),
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/preferences")
async def list_preferences(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await ListPreferencesUseCase(session).execute(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/status")
async def learning_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await GetLearningStatusUseCase(session).execute(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/metrics")
async def learning_metrics(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> dict:
    engine = LearningFactory.create_memory()
    snap = engine.metrics.snap
    return success_response(
        {
            "captures": snap.captures,
            "processed_artifacts": snap.processed_artifacts,
            "stored_artifacts": snap.stored_artifacts,
            "examples_grown": snap.examples_grown,
            "rules_grown": snap.rules_grown,
            "preferences_grown": snap.preferences_grown,
            "organization_id": str(current_user.organization_id),
        },
        request_id=getattr(request.state, "request_id", ""),
    )
