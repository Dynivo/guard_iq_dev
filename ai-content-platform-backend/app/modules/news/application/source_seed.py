"""Upsert enterprise free news sources for an organization from YAML catalog."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.news import NewsSource
from app.modules.news.application.source_catalog import load_enterprise_source_catalog


async def ensure_catalog_sources(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    enabled_default: bool | None = None,
) -> dict[str, int]:
    """Insert missing catalog sources; refresh metadata for existing names.

    Returns counts: created, updated, skipped.
    """
    created = updated = skipped = 0
    for entry in load_enterprise_source_catalog():
        result = await session.execute(
            select(NewsSource).where(
                NewsSource.organization_id == org_id,
                NewsSource.name == entry["name"],
            )
        )
        existing = result.scalar_one_or_none()
        config = dict(entry["config"])
        if entry.get("api_key_name"):
            config.setdefault("api_key_name", entry["api_key_name"])
        config.setdefault("catalog_id", entry["catalog_id"])
        config.setdefault("category", entry["category"])

        fields: dict[str, Any] = {
            "connector_type": entry["connector_type"],
            "config_json": config,
            "schedule_cron": entry["schedule_cron"],
            "category": entry["category"],
            "credibility_score": entry["credibility_score"],
            "priority": entry["priority"],
            "api_key_name": entry.get("api_key_name"),
            "authority": entry["authority"],
            "reliability": entry["reliability"],
            "trust": entry["trust"],
        }
        if enabled_default is not None:
            fields["enabled"] = enabled_default
        else:
            fields["enabled"] = bool(entry.get("enabled", True))

        if existing is None:
            # Prefer HN API over duplicate legacy "Hacker News" RSS if that name exists
            if entry["name"] == "Hacker News (RSS)":
                legacy = await session.execute(
                    select(NewsSource).where(
                        NewsSource.organization_id == org_id,
                        NewsSource.name == "Hacker News",
                    )
                )
                legacy_src = legacy.scalar_one_or_none()
                if legacy_src is not None:
                    for key, value in fields.items():
                        setattr(legacy_src, key, value)
                    legacy_src.name = entry["name"]
                    updated += 1
                    continue
            session.add(NewsSource(organization_id=org_id, name=entry["name"], **fields))
            created += 1
            continue

        # Refresh catalog metadata / URLs without wiping user enabled flag
        for key, value in fields.items():
            if key == "enabled":
                continue
            setattr(existing, key, value)
        updated += 1

    await session.flush()
    return {"created": created, "updated": updated, "skipped": skipped}
