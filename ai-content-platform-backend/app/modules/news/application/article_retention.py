"""Retention sweep — permanently removes not-relevant articles once they're
past IRRELEVANT_ARTICLE_RETENTION_DAYS old.

Deliberately scoped to status="irrelevant" only: relevant articles (hidden
or not) are left alone since they're the actual content pipeline and their
reasoning is useful signal — see the Hide feature in articles.py for how
relevant articles get decluttered without being deleted. Irrelevant
articles have no ongoing value once classified, so hard-deleting them (not
just hiding) is the intended behavior here.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.news import (
    Article,
    ArticleEntity,
    ArticleEvent,
    ArticleRawPayload,
    ClusterMember,
)
from app.infrastructure.postgres.models.intelligence import RelevanceScore

logger = get_logger(__name__)

_MAX_PER_SWEEP = 500


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def purge_old_irrelevant_articles(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    retention_days = settings.IRRELEVANT_ARTICLE_RETENTION_DAYS
    if retention_days <= 0:
        return {"checked": 0, "deleted": 0}

    cutoff = _utc_now() - timedelta(days=retention_days)

    # Never delete an article a draft still points at, even if it's since
    # been marked irrelevant.
    referenced = {
        str(r) for (r,) in (
            await session.execute(select(Draft.article_id).where(Draft.article_id.isnot(None)))
        ).all()
    }

    rows = (
        await session.execute(
            select(Article.id)
            .where(Article.status == "irrelevant", Article.created_at < cutoff)
            .limit(_MAX_PER_SWEEP)
        )
    ).scalars().all()
    ids = [str(r) for r in rows if str(r) not in referenced]
    if not ids:
        return {"checked": len(rows), "deleted": 0}

    for model in (ArticleRawPayload, ClusterMember, ArticleEntity, ArticleEvent, RelevanceScore):
        await session.execute(
            model.__table__.delete().where(model.article_id.in_(ids))
        )
    await session.execute(Article.__table__.delete().where(Article.id.in_(ids)))
    await session.commit()

    return {"checked": len(rows), "deleted": len(ids)}


async def article_retention_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_seconds: int | None = None,
) -> None:
    """Long-running background sweep — started once from app lifespan."""
    interval = interval_seconds or get_settings().ARTICLE_RETENTION_SWEEP_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(interval)
        try:
            async with session_factory() as session:
                result = await purge_old_irrelevant_articles(session)
                if result["deleted"]:
                    logger.info("Article retention sweep: %s", result)
        except Exception:  # noqa: BLE001
            logger.exception("Article retention sweep failed")
