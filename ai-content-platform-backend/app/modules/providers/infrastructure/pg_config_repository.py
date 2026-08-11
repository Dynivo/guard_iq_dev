"""PostgreSQL provider config repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.ai_ops import ProviderConfig


class PgProviderConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_org(self, org_id: uuid.UUID) -> list[dict]:
        rows = (
            (
                await self._session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.organization_id == org_id,
                        ProviderConfig.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        return [self._to_dict(r) for r in rows]

    async def get_for_capability(self, org_id: uuid.UUID, capability: str) -> dict | None:
        row = (
            await self._session.execute(
                select(ProviderConfig)
                .where(
                    ProviderConfig.organization_id == org_id,
                    ProviderConfig.capability == capability,
                    ProviderConfig.is_active.is_(True),
                )
                .order_by(ProviderConfig.priority.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return self._to_dict(row) if row else None

    async def upsert(self, org_id: uuid.UUID, config: dict) -> uuid.UUID:
        existing = await self.get_for_capability(org_id, str(config["capability"]))
        if existing:
            row = (
                await self._session.execute(
                    select(ProviderConfig).where(ProviderConfig.id == uuid.UUID(existing["id"]))
                )
            ).scalar_one()
            row.provider = str(config["provider"])
            row.model = str(config["model"])
            row.config_json = config.get("config_json")
            row.is_active = bool(config.get("is_active", True))
            row.priority = int(config.get("priority", 0))
            await self._session.flush()
            return row.id
        row = ProviderConfig(
            organization_id=org_id,
            capability=str(config["capability"]),
            provider=str(config["provider"]),
            model=str(config["model"]),
            config_json=config.get("config_json"),
            is_active=bool(config.get("is_active", True)),
            priority=int(config.get("priority", 0)),
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    @staticmethod
    def _to_dict(row: ProviderConfig) -> dict:
        return {
            "id": str(row.id),
            "organization_id": str(row.organization_id),
            "capability": row.capability,
            "provider": row.provider,
            "model": row.model,
            "config_json": row.config_json or {},
            "is_active": row.is_active,
            "priority": row.priority,
        }
