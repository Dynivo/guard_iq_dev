"""Carousel generation and listing routes — Carousel Engine (M12)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.carousel.application.list_use_cases import (
    GetCarouselUseCase,
    ListCarouselsUseCase,
)
from app.modules.carousel.application.service import CarouselGenerationService

router = APIRouter(tags=["carousels"])


class GenerateCarouselBody(BaseModel):
    size: str = Field(default="1080x1350")
    typography_asset_id: uuid.UUID | None = None


@router.post("/drafts/{draft_id}/carousels/generate")
async def generate_carousel(
    draft_id: uuid.UUID,
    request: Request,
    size: str = Query("1080x1350"),
    typography_asset_id: uuid.UUID | None = Query(None),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = CarouselGenerationService(session)
    result = await service.generate(
        current_user.organization_id,
        draft_id,
        size=size,
        typography_asset_id=typography_asset_id,
        correlation_id=getattr(request.state, "request_id", "") or "",
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.get("/carousels")
async def list_carousels(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await ListCarouselsUseCase(session).execute(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/carousels/{deck_id}")
async def get_carousel(
    deck_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await GetCarouselUseCase(session).execute(current_user.organization_id, deck_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))
