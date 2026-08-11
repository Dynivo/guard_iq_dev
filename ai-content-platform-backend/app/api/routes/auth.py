"""Auth routes: login, refresh, get current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from app.api.schemas.envelope import success_response
from app.infrastructure.postgres import get_async_session
from app.modules.auth.application.use_cases import LoginUseCase, RefreshTokenUseCase
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.auth.infrastructure.repositories import (
    PgMembershipRepository,
    PgUserRepository,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Authenticate with email and password, receive access + refresh tokens."""
    user_repo = PgUserRepository(session)
    membership_repo = PgMembershipRepository(session)
    use_case = LoginUseCase(user_repo, membership_repo)
    token_pair = await use_case.execute(body.email, body.password)
    request_id = getattr(request.state, "request_id", "")
    return success_response(
        TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
        ).model_dump(),
        request_id=request_id,
    )


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Exchange a valid refresh token for a new token pair."""
    user_repo = PgUserRepository(session)
    membership_repo = PgMembershipRepository(session)
    use_case = RefreshTokenUseCase(user_repo, membership_repo)
    token_pair = await use_case.execute(body.refresh_token)
    request_id = getattr(request.state, "request_id", "")
    return success_response(
        TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
        ).model_dump(),
        request_id=request_id,
    )


@router.get("/me")
async def get_me(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Return the authenticated user's profile and org context."""
    request_id = getattr(request.state, "request_id", "")
    return success_response(
        UserResponse(
            user_id=str(current_user.user_id),
            email=current_user.email,
            display_name=current_user.display_name,
            organization_id=str(current_user.organization_id),
            role=current_user.role,
        ).model_dump(),
        request_id=request_id,
    )
