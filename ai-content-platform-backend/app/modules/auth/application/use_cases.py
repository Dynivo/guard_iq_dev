"""Auth use cases: login, refresh, get-current-user."""

from __future__ import annotations

import uuid

from app.core.constants import MembershipRole
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.security.jwt import create_access_token, create_refresh_token, decode_token
from app.core.security.password import verify_password
from app.modules.auth.domain.entities import AuthenticatedUser, TokenPair
from app.modules.auth.domain.ports import MembershipRepository, UserRepository

logger = get_logger(__name__)


class LoginUseCase:
    """Authenticate a user by email and password, return a token pair."""

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
    ) -> None:
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, email: str, password: str) -> TokenPair:
        user = await self._user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            logger.warning("Login failed for email=%s", email)
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        membership = await self._membership_repo.get_primary_membership(user.id)
        role = membership.role if membership else MembershipRole.VIEWER
        org_id = str(membership.organization_id) if membership else str(user.organization_id)

        extra_claims = {"org_id": org_id, "role": role}
        access_token = create_access_token(subject=str(user.id), extra_claims=extra_claims)
        refresh_token = create_refresh_token(subject=str(user.id))

        logger.info("User logged in: user_id=%s org_id=%s", user.id, org_id)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)


class RefreshTokenUseCase:
    """Issue a new access token from a valid refresh token."""

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
    ) -> None:
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, token_type="refresh")
        user_id = uuid.UUID(payload["sub"])
        user = await self._user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or deactivated")

        membership = await self._membership_repo.get_primary_membership(user.id)
        role = membership.role if membership else MembershipRole.VIEWER
        org_id = str(membership.organization_id) if membership else str(user.organization_id)

        extra_claims = {"org_id": org_id, "role": role}
        new_access = create_access_token(subject=str(user.id), extra_claims=extra_claims)
        new_refresh = create_refresh_token(subject=str(user.id))

        return TokenPair(access_token=new_access, refresh_token=new_refresh)


class GetCurrentUserUseCase:
    """Resolve an access token into an AuthenticatedUser value object."""

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
    ) -> None:
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, token: str) -> AuthenticatedUser:
        payload = decode_token(token, token_type="access")
        user_id = uuid.UUID(payload["sub"])
        user = await self._user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or deactivated")

        org_id = uuid.UUID(payload.get("org_id", str(user.organization_id)))
        role = MembershipRole(payload.get("role", MembershipRole.VIEWER))

        return AuthenticatedUser(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            organization_id=org_id,
            role=role,
        )
