"""Auth module ports (interfaces). Domain layer — no infrastructure imports."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.auth.domain.records import MembershipRecord, UserRecord


class UserRepository(Protocol):
    """Port for user persistence operations."""

    async def get_by_email(self, email: str) -> UserRecord | None: ...

    async def get_by_id(self, user_id: uuid.UUID) -> UserRecord | None: ...

    async def create(self, email: str, display_name: str, hashed_password: str) -> UserRecord: ...


class MembershipRepository(Protocol):
    """Port for membership lookups."""

    async def get_by_user_and_org(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> MembershipRecord | None: ...

    async def get_primary_membership(self, user_id: uuid.UUID) -> MembershipRecord | None: ...
