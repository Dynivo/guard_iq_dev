"""Postgres-backed repositories for the organization module."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.postgres.models.identity import Membership, Organization
from app.modules.organization.domain.records import OrgMemberRecord, OrganizationRecord


def _to_org(org: Organization) -> OrganizationRecord:
    return OrganizationRecord(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        settings_json=org.settings_json,
    )


class PgOrganizationRepository:
    """SQLAlchemy-based organization repository returning domain records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, org_id: uuid.UUID) -> OrganizationRecord | None:
        stmt = select(Organization).where(Organization.id == org_id)
        result = await self._session.execute(stmt)
        org = result.scalar_one_or_none()
        return _to_org(org) if org else None

    async def get_by_slug(self, slug: str) -> OrganizationRecord | None:
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self._session.execute(stmt)
        org = result.scalar_one_or_none()
        return _to_org(org) if org else None

    async def list_members(self, org_id: uuid.UUID) -> list[OrgMemberRecord]:
        stmt = (
            select(Membership)
            .options(selectinload(Membership.user))
            .where(Membership.organization_id == org_id, Membership.is_active.is_(True))
        )
        result = await self._session.execute(stmt)
        members = list(result.scalars().all())
        out: list[OrgMemberRecord] = []
        for m in members:
            out.append(
                OrgMemberRecord(
                    user_id=m.user_id,
                    email=m.user.email if m.user else "",
                    display_name=m.user.display_name if m.user else "",
                    role=m.role,
                )
            )
        return out
