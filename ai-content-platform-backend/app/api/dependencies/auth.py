"""FastAPI dependencies for authentication and org context."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.observability.correlation import set_organization_id
from app.infrastructure.postgres import get_async_session
from app.modules.auth.application.use_cases import GetCurrentUserUseCase
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.auth.infrastructure.repositories import (
    PgMembershipRepository,
    PgUserRepository,
)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> AuthenticatedUser:
    """Extract and validate the current user from the Authorization header."""
    if credentials is None:
        raise AuthenticationError("Authorization header missing")

    user_repo = PgUserRepository(session)
    membership_repo = PgMembershipRepository(session)
    use_case = GetCurrentUserUseCase(user_repo, membership_repo)
    user = await use_case.execute(credentials.credentials)
    set_organization_id(str(user.organization_id))
    return user
