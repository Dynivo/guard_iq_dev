"""Brand kit routes: get, patch, profile template."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.brand_kit import BrandKitUpdateRequest
from app.api.schemas.envelope import success_response
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.organization.application.brand_kit_use_cases import (
    GetBrandKitUseCase,
    UpdateBrandKitUseCase,
    get_profile_template,
)
from app.modules.organization.infrastructure.brand_kit_repository import PgBrandKitRepository

router = APIRouter(prefix="/brand-kits", tags=["brand-kits"])
alias_router = APIRouter(prefix="/brand-kit", tags=["brand-kits"])


@router.get("/current")
@alias_router.get("")
async def get_brand_kit(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Get the brand kit for the current organization."""
    repo = PgBrandKitRepository(session)
    use_case = GetBrandKitUseCase(repo)
    kit = await use_case.execute(current_user.organization_id)
    request_id = getattr(request.state, "request_id", "")
    return success_response(kit, request_id=request_id)


@router.patch("/current")
@alias_router.patch("")
async def update_brand_kit(
    body: BrandKitUpdateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Partially update the brand kit for the current organization."""
    repo = PgBrandKitRepository(session)
    use_case = UpdateBrandKitUseCase(repo)
    updates = body.model_dump(exclude_unset=True)
    kit = await use_case.execute(current_user.organization_id, updates)
    request_id = getattr(request.state, "request_id", "")
    return success_response(kit, request_id=request_id)


@router.get("/profile-template")
@alias_router.get("/profile-template")
async def brand_profile_template(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Prompt + outline for generating a compatible brand profile (Claude/ChatGPT)."""
    _ = current_user
    request_id = getattr(request.state, "request_id", "")
    return success_response(get_profile_template(), request_id=request_id)
