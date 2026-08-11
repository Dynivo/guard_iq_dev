"""Content module repositories — drafts and variations persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.content import Draft, DraftVariation


class PgDraftRepository:
    """Postgres repository for drafts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, draft: Draft) -> Draft:
        self._session.add(draft)
        await self._session.flush()
        return draft

    async def get_by_id(
        self, draft_id: uuid.UUID, org_id: uuid.UUID | None = None
    ) -> Draft | None:
        stmt = select(Draft).where(Draft.id == draft_id)
        if org_id is not None:
            stmt = stmt.where(Draft.organization_id == org_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self, draft_id: uuid.UUID, fields: dict, org_id: uuid.UUID | None = None
    ) -> Draft | None:
        draft = await self.get_by_id(draft_id, org_id=org_id)
        if draft is None:
            return None
        for key, value in fields.items():
            if hasattr(draft, key):
                setattr(draft, key, value)
        await self._session.flush()
        return draft

    async def list_by_org(
        self, org_id: uuid.UUID, status: str | None = None
    ) -> list[Draft]:
        stmt = select(Draft).where(Draft.organization_id == org_id)
        if status:
            stmt = stmt.where(Draft.status == status)
        stmt = stmt.order_by(Draft.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PgDraftVariationRepository:
    """Postgres repository for draft variations (alternative hooks)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(self, variations: list[DraftVariation]) -> list[DraftVariation]:
        self._session.add_all(variations)
        await self._session.flush()
        return variations

    async def get_by_draft(self, draft_id: uuid.UUID) -> list[DraftVariation]:
        stmt = (
            select(DraftVariation)
            .where(DraftVariation.draft_id == draft_id)
            .order_by(DraftVariation.variation_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
