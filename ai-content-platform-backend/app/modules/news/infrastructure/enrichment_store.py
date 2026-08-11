"""Persist news enrichment rows (entities, events, trends, timelines)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.postgres.models.news import (
    ArticleEntity,
    ArticleEvent,
    NewsTopicTrend,
    StoryTimelineRow,
)

logger = get_logger(__name__)


class PgEnrichmentWriter:
    """Writes pipeline enrichment outputs into durable Postgres tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist_article_enrichment(
        self,
        *,
        org_id: uuid.UUID,
        article_id: uuid.UUID,
        article_url: str,
        metadata: dict[str, Any] | None,
    ) -> None:
        meta = metadata or {}
        entities = meta.get("entities") or {}
        if isinstance(entities, dict):
            for etype, values in entities.items():
                if not isinstance(values, (list, tuple)):
                    continue
                for value in values:
                    if not value:
                        continue
                    self._session.add(
                        ArticleEntity(
                            organization_id=org_id,
                            article_id=article_id,
                            article_url=article_url,
                            entity_type=str(etype)[:50],
                            value=str(value)[:500],
                            confidence=0.85 if etype == "cves" else 0.7,
                        )
                    )

        events = meta.get("events") or []
        if isinstance(events, list):
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                et = ev.get("event_type") or ev.get("type")
                if not et:
                    continue
                self._session.add(
                    ArticleEvent(
                        organization_id=org_id,
                        article_id=article_id,
                        article_url=article_url,
                        event_type=str(et)[:50],
                        confidence=float(ev.get("confidence") or 0.0),
                        evidence=str(ev.get("evidence") or "")[:4000] or None,
                        metadata_json=ev,
                    )
                )

        await self._session.flush()

    async def persist_trends(
        self,
        *,
        org_id: uuid.UUID,
        trends: list[dict[str, Any]],
        window_label: str = "ingest_run",
    ) -> int:
        count = 0
        for t in trends:
            if not isinstance(t, dict):
                continue
            topic_key = t.get("topic_key")
            if not topic_key:
                continue
            self._session.add(
                NewsTopicTrend(
                    organization_id=org_id,
                    topic_key=str(topic_key)[:255],
                    window_label=window_label,
                    metrics_json=t,
                )
            )
            count += 1
        if count:
            await self._session.flush()
        return count

    async def persist_timelines(
        self,
        *,
        org_id: uuid.UUID,
        timelines: list[dict[str, Any]],
    ) -> int:
        count = 0
        for tl in timelines:
            if not isinstance(tl, dict):
                continue
            story_id = tl.get("story_id")
            label = tl.get("label")
            if not story_id or not label:
                continue
            started = tl.get("started_at")
            updated = tl.get("updated_at")
            from datetime import datetime

            def _parse(v: Any) -> datetime | None:
                if v is None:
                    return None
                if isinstance(v, datetime):
                    return v
                try:
                    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                except Exception:
                    return None

            self._session.add(
                StoryTimelineRow(
                    organization_id=org_id,
                    story_id=str(story_id)[:100],
                    label=str(label)[:500],
                    article_urls=tl.get("article_urls") or [],
                    events=tl.get("events") or [],
                    cohesion=float(tl.get("cohesion") or 0.0),
                    started_at=_parse(started),
                    updated_at_story=_parse(updated),
                    metadata_json=tl,
                )
            )
            count += 1
        if count:
            await self._session.flush()
        return count


async def list_org_trends(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return latest trend snapshot per topic_key for an org."""
    from sqlalchemy import select

    rows = (
        await session.execute(
            select(NewsTopicTrend)
            .where(NewsTopicTrend.organization_id == org_id)
            .order_by(NewsTopicTrend.created_at.desc())
            .limit(limit * 5)
        )
    ).scalars().all()

    latest: dict[str, NewsTopicTrend] = {}
    for row in rows:
        if row.topic_key not in latest:
            latest[row.topic_key] = row

    out: list[dict[str, Any]] = []
    for key, row in list(latest.items())[:limit]:
        metrics = row.metrics_json if isinstance(row.metrics_json, dict) else {}
        out.append(
            {
                "id": str(row.id),
                "topic_key": key,
                "window_label": row.window_label,
                "metrics": metrics,
                "growth": metrics.get("growth"),
                "momentum": metrics.get("momentum"),
                "velocity": metrics.get("velocity"),
                "popularity": metrics.get("popularity"),
                "predicted_trend": metrics.get("predicted_trend"),
                "article_count": metrics.get("article_count"),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    out.sort(key=lambda x: float(x.get("momentum") or 0), reverse=True)
    return out
