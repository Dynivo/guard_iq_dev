"""Learning list use cases — application layer over repositories."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.learning import (
    Example,
    KnowledgeSignalRow,
    LearningEventRow,
    PreferenceUpdateRow,
    Rule,
    WritingPreference,
)
from app.modules.learning.infrastructure.repositories import (
    PgExampleLibrary,
    PgPreferenceStore,
    PgRulesLibrary,
)


class ListExamplesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._lib = PgExampleLibrary(session)

    async def execute(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self._lib.list_active(org_id)


class ListRulesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._lib = PgRulesLibrary(session)

    async def execute(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self._lib.list_active(org_id)


class ListPreferencesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._lib = PgPreferenceStore(session)

    async def execute(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self._lib.list_active(org_id)


class GetLearningStatusUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _lifecycle_counts(self, model, org_id: uuid.UUID) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(model.lifecycle, func.count())
                .where(model.organization_id == org_id)
                .group_by(model.lifecycle)
            )
        ).all()
        return {str(life or "candidate"): int(cnt) for life, cnt in rows}

    async def execute(self, org_id: uuid.UUID) -> dict[str, Any]:
        examples = (
            await self._session.execute(
                select(func.count())
                .select_from(Example)
                .where(Example.organization_id == org_id, Example.is_active.is_(True))
            )
        ).scalar_one()
        rules = (
            await self._session.execute(
                select(func.count())
                .select_from(Rule)
                .where(Rule.organization_id == org_id, Rule.is_active.is_(True))
            )
        ).scalar_one()
        prefs = (
            await self._session.execute(
                select(func.count())
                .select_from(WritingPreference)
                .where(
                    WritingPreference.organization_id == org_id,
                    WritingPreference.is_active.is_(True),
                )
            )
        ).scalar_one()
        events = (
            await self._session.execute(
                select(func.count())
                .select_from(LearningEventRow)
                .where(LearningEventRow.organization_id == org_id)
            )
        ).scalar_one()
        updates = (
            await self._session.execute(
                select(func.count())
                .select_from(PreferenceUpdateRow)
                .where(PreferenceUpdateRow.organization_id == org_id)
            )
        ).scalar_one()
        signals = (
            await self._session.execute(
                select(func.count())
                .select_from(KnowledgeSignalRow)
                .where(KnowledgeSignalRow.organization_id == org_id)
            )
        ).scalar_one()
        return {
            "organization_id": str(org_id),
            "examples": int(examples or 0),
            "rules": int(rules or 0),
            "preferences": int(prefs or 0),
            "signals": int(signals or 0),
            "learning_events": int(events or 0),
            "preference_updates": int(updates or 0),
            "lifecycle": {
                "examples": await self._lifecycle_counts(Example, org_id),
                "rules": await self._lifecycle_counts(Rule, org_id),
                "preferences": await self._lifecycle_counts(WritingPreference, org_id),
                "signals": await self._lifecycle_counts(KnowledgeSignalRow, org_id),
            },
        }


class UpdateExampleUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._lib = PgExampleLibrary(session)

    async def execute(
        self, org_id: uuid.UUID, example_id: uuid.UUID, **fields: Any
    ) -> dict[str, Any]:
        from app.core.exceptions import NotFoundError

        updated = await self._lib.update(org_id, example_id, **fields)
        if updated is None:
            raise NotFoundError("Example", str(example_id))
        return updated


class UpdateRuleUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._lib = PgRulesLibrary(session)

    async def execute(
        self, org_id: uuid.UUID, rule_id: uuid.UUID, **fields: Any
    ) -> dict[str, Any]:
        from app.core.exceptions import NotFoundError

        updated = await self._lib.update(org_id, rule_id, **fields)
        if updated is None:
            raise NotFoundError("Rule", str(rule_id))
        return updated

