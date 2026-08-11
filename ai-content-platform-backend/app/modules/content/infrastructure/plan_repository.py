"""ContentPlan persistence adapters."""

from __future__ import annotations

import uuid
from app.infrastructure.postgres.models import content as orm
from app.modules.content.domain.models import ContentPlan


class InMemoryContentPlanRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, ContentPlan] = {}

    async def save(self, plan: ContentPlan) -> ContentPlan:
        self._store[plan.id] = plan
        return plan

    async def get_by_id(
        self, org_id: uuid.UUID, plan_id: uuid.UUID
    ) -> ContentPlan | None:
        plan = self._store.get(plan_id)
        if plan is None or plan.organization_id != org_id:
            return None
        return plan


class PgContentPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, plan: ContentPlan) -> ContentPlan:
        row = await self._session.get(orm.ContentPlan, plan.id)
        payload = plan.to_dict()
        if row is None:
            row = orm.ContentPlan(
                id=plan.id,
                organization_id=plan.organization_id,
                article_id=plan.article_id,
                content_type=plan.content_type.value,
                angle=plan.strategy[:500] if plan.strategy else None,
                target_audience=plan.audience.value,
                plan_json=payload,
                status=plan.status.value,
                confidence=plan.confidence,
                strategy_action=plan.strategy_action.value,
                rejected_reason=plan.rejected_reason or None,
                correlation_id=plan.correlation_id or None,
            )
            self._session.add(row)
        else:
            row.content_type = plan.content_type.value
            row.angle = plan.strategy[:500] if plan.strategy else None
            row.target_audience = plan.audience.value
            row.plan_json = payload
            row.status = plan.status.value
            row.confidence = plan.confidence
            row.strategy_action = plan.strategy_action.value
            row.rejected_reason = plan.rejected_reason or None
            row.correlation_id = plan.correlation_id or None
            row.article_id = plan.article_id
        await self._session.flush()
        return plan

    async def get_by_id(
        self, org_id: uuid.UUID, plan_id: uuid.UUID
    ) -> ContentPlan | None:
        stmt = select(orm.ContentPlan).where(
            orm.ContentPlan.id == plan_id,
            orm.ContentPlan.organization_id == org_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None or not row.plan_json:
            return None
        return ContentPlan.from_dict(row.plan_json)
