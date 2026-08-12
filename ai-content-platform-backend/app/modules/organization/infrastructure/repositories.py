"""Postgres-backed repositories for the organization module."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.identity import Organization
from app.modules.organization.domain.records import OrganizationRecord


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
