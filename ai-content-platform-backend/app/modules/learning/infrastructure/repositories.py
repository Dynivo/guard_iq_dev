"""Learning library repositories."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.learning import Example, Rule, WritingPreference

_VISIBLE_LIFECYCLES = ("candidate", "verified", "approved", "deprecated")


class PgExampleLibrary:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _promote_review_candidates(self, org_id: uuid.UUID) -> None:
        """Approve/reject already validated the draft — promote stored candidates."""
        await self._session.execute(
            update(Example)
            .where(
                Example.organization_id == org_id,
                Example.lifecycle == "candidate",
                Example.created_from_review.is_(True),
            )
            .values(lifecycle="approved", is_active=True)
        )

    async def list_active(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        await self._promote_review_candidates(org_id)
        rows = (
            await self._session.execute(
                select(Example)
                .where(
                    Example.organization_id == org_id,
                    Example.lifecycle.in_(_VISIBLE_LIFECYCLES),
                )
                .order_by(Example.created_at.desc())
            )
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "text": r.text,
                "hook": r.hook,
                "content_type": r.content_type,
                "weight": r.weight,
                "confidence": r.confidence,
                "lifecycle": r.lifecycle,
                "is_active": r.is_active,
                "approval_count": r.approval_count,
                "usage_count": r.usage_count,
                "success_rate": r.success_rate,
            }
            for r in rows
        ]

    async def update(
        self,
        org_id: uuid.UUID,
        example_id: uuid.UUID,
        *,
        text: str | None = None,
        hook: str | None = None,
        weight: float | None = None,
        lifecycle: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(Example).where(
                    Example.id == example_id,
                    Example.organization_id == org_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if text is not None:
            row.text = text
        if hook is not None:
            row.hook = hook
        if weight is not None:
            row.weight = weight
        if lifecycle is not None:
            row.lifecycle = lifecycle
        if is_active is not None:
            row.is_active = is_active
        row.version = int(row.version or 1) + 1
        await self._session.flush()
        return {
            "id": str(row.id),
            "text": row.text,
            "hook": row.hook,
            "content_type": row.content_type,
            "weight": row.weight,
            "lifecycle": row.lifecycle,
            "is_active": row.is_active,
            "version": row.version,
        }


class PgRulesLibrary:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _promote_review_candidates(self, org_id: uuid.UUID) -> None:
        await self._session.execute(
            update(Rule)
            .where(
                Rule.organization_id == org_id,
                Rule.lifecycle == "candidate",
                Rule.created_from_review.is_(True),
            )
            .values(lifecycle="approved", is_active=True)
        )

    async def list_active(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        await self._promote_review_candidates(org_id)
        rows = (
            await self._session.execute(
                select(Rule)
                .where(
                    Rule.organization_id == org_id,
                    Rule.lifecycle.in_(_VISIBLE_LIFECYCLES),
                )
                .order_by(Rule.created_at.desc())
            )
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "category": r.category,
                "text": r.text,
                "priority": r.priority,
                "confidence": r.confidence,
                "lifecycle": r.lifecycle,
                "is_active": r.is_active,
            }
            for r in rows
        ]

    async def update(
        self,
        org_id: uuid.UUID,
        rule_id: uuid.UUID,
        *,
        text: str | None = None,
        category: str | None = None,
        priority: int | None = None,
        lifecycle: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(Rule).where(
                    Rule.id == rule_id,
                    Rule.organization_id == org_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if text is not None:
            row.text = text
        if category is not None:
            row.category = category
        if priority is not None:
            row.priority = priority
        if lifecycle is not None:
            row.lifecycle = lifecycle
        if is_active is not None:
            row.is_active = is_active
        row.version = int(row.version or 1) + 1
        await self._session.flush()
        return {
            "id": str(row.id),
            "category": row.category,
            "text": row.text,
            "priority": row.priority,
            "lifecycle": row.lifecycle,
            "is_active": row.is_active,
            "version": row.version,
        }


class PgPreferenceStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _promote_review_candidates(self, org_id: uuid.UUID) -> None:
        await self._session.execute(
            update(WritingPreference)
            .where(
                WritingPreference.organization_id == org_id,
                WritingPreference.lifecycle == "candidate",
                WritingPreference.created_from_review.is_(True),
            )
            .values(lifecycle="approved", is_active=True)
        )

    async def list_active(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        await self._promote_review_candidates(org_id)
        rows = (
            await self._session.execute(
                select(WritingPreference)
                .where(
                    WritingPreference.organization_id == org_id,
                    WritingPreference.lifecycle.in_(_VISIBLE_LIFECYCLES),
                )
                .order_by(WritingPreference.created_at.desc())
            )
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "category": r.category,
                "preference": r.preference,
                "confidence": r.confidence,
                "lifecycle": r.lifecycle,
                "is_active": r.is_active,
                "approval_count": r.approval_count,
                "usage_count": r.usage_count,
                "success_rate": r.success_rate,
            }
            for r in rows
        ]
