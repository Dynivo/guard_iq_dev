"""Postgres-backed brand kit repository returning domain records."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.branding import BrandKit
from app.modules.organization.domain.records import BrandKitRecord


def _to_record(kit: BrandKit) -> BrandKitRecord:
    return BrandKitRecord(
        id=kit.id,
        organization_id=kit.organization_id,
        name=kit.name,
        primary_color=kit.primary_color,
        secondary_color=kit.secondary_color,
        accent_color=kit.accent_color,
        font_heading=kit.font_heading,
        font_body=kit.font_body,
        logo_object_key=kit.logo_object_key,
        tone_json=kit.tone_json,
        footer_text=kit.footer_text,
        services_line=kit.services_line,
        client_profile_path=kit.client_profile_path,
        client_profile_md=kit.client_profile_md,
        extra_settings=kit.extra_settings,
        description=kit.description,
    )


class PgBrandKitRepository:
    """SQLAlchemy-based brand kit repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_org_id(self, org_id: uuid.UUID) -> BrandKitRecord | None:
        stmt = select(BrandKit).where(BrandKit.organization_id == org_id).limit(1)
        result = await self._session.execute(stmt)
        kit = result.scalar_one_or_none()
        return _to_record(kit) if kit else None

    async def get_by_id(self, kit_id: uuid.UUID) -> BrandKitRecord | None:
        stmt = select(BrandKit).where(BrandKit.id == kit_id)
        result = await self._session.execute(stmt)
        kit = result.scalar_one_or_none()
        return _to_record(kit) if kit else None

    async def update(self, kit_id: uuid.UUID, fields: dict[str, Any]) -> BrandKitRecord | None:
        allowed = {
            "name", "primary_color", "secondary_color", "accent_color",
            "font_heading", "font_body", "logo_object_key", "tone_json",
            "footer_text", "services_line", "client_profile_path",
            "client_profile_md", "description", "extra_settings",
        }
        safe_fields = {k: v for k, v in fields.items() if k in allowed}
        if safe_fields:
            stmt = update(BrandKit).where(BrandKit.id == kit_id).values(**safe_fields)
            await self._session.execute(stmt)
            await self._session.flush()
        return await self.get_by_id(kit_id)
