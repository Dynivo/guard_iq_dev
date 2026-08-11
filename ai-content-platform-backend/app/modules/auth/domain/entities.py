"""Auth domain value objects."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.constants import MembershipRole


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents the currently authenticated user with org context."""

    user_id: uuid.UUID
    email: str
    display_name: str
    organization_id: uuid.UUID
    role: MembershipRole


@dataclass(frozen=True)
class TokenPair:
    """Access + refresh token bundle returned after authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
