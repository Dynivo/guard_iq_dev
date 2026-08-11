"""Postgres-backed repositories for the auth module.

Maps ORM models to domain records so the domain layer never imports SQLAlchemy.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.identity import Membership, User
from app.modules.auth.domain.records import MembershipRecord, UserRecord


def _to_user_record(user: User) -> UserRecord:
    return UserRecord(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        password_hash=user.password_hash,
        is_active=user.is_active,
        organization_id=user.organization_id,
    )


def _to_membership_record(m: Membership) -> MembershipRecord:
    return MembershipRecord(
        id=m.id,
        user_id=m.user_id,
        organization_id=m.organization_id,
        role=m.role,
        is_active=m.is_active,
    )


class PgUserRepository:
    """SQLAlchemy-based user repository returning domain records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> UserRecord | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        return _to_user_record(user) if user else None

    async def get_by_id(self, user_id: uuid.UUID) -> UserRecord | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        return _to_user_record(user) if user else None

    async def create(self, email: str, display_name: str, hashed_password: str) -> UserRecord:
        raise NotImplementedError("User creation goes through seed/admin flows")


class PgMembershipRepository:
    """SQLAlchemy-based membership repository returning domain records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_and_org(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> MembershipRecord | None:
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
            Membership.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_membership_record(row) if row else None

    async def get_primary_membership(self, user_id: uuid.UUID) -> MembershipRecord | None:
        stmt = (
            select(Membership)
            .where(Membership.user_id == user_id, Membership.is_active.is_(True))
            .order_by(Membership.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_membership_record(row) if row else None
