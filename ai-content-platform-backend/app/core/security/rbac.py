"""Role-based access control helpers.

Roles follow a strict hierarchy: owner > editor > viewer.
`require_role` returns a FastAPI dependency that rejects requests whose
membership role is below the required minimum.

Note: imports get_current_user lazily to avoid core→api circular imports.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.core.constants import MembershipRole
from app.core.exceptions import AuthorizationError
from app.modules.auth.domain.entities import AuthenticatedUser

_ROLE_HIERARCHY: dict[MembershipRole, int] = {
    MembershipRole.VIEWER: 0,
    MembershipRole.EDITOR: 1,
    MembershipRole.OWNER: 2,
}


def _role_level(role: MembershipRole | str) -> int:
    if isinstance(role, str):
        try:
            role = MembershipRole(role)
        except ValueError:
            return -1
    return _ROLE_HIERARCHY.get(role, -1)


def require_role(minimum: MembershipRole) -> Callable[..., AuthenticatedUser]:
    """FastAPI dependency that enforces a minimum role on the current user."""

    from app.api.dependencies.auth import get_current_user

    async def _check(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if _role_level(current_user.role) < _role_level(minimum):
            raise AuthorizationError(
                f"Role '{minimum}' or higher required; you have '{current_user.role}'"
            )
        return current_user

    return _check
