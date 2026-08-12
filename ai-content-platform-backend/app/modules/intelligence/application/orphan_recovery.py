"""Recover articles orphaned at status="scored" — the relevance task that
should have followed ingestion was lost (e.g. an API restart killed the
fire-and-forget asyncio task before it ran) and nothing else ever retries it.

Mirrors app/modules/image/application/orphan_recovery.py's pattern for image
batches: a bounded sweep, re-dispatched through the same semaphore-gated path
used for normal auto-scoring.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.postgres.models.news import Article

logger = get_logger(__name__)

# Grace period before an article sitting at status="scored" is considered
# orphaned rather than just still legitimately in flight.
_RECOVERY_AFTER = timedelta(seconds=90)
# Cap per sweep — each recovered article is a real LLM call.
_MAX_PER_SWEEP = 20
# How often the background loop re-checks for orphans.
_SWEEP_INTERVAL_SECONDS = 600


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def recover_orphaned_relevance_scoring(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    limit: int = _MAX_PER_SWEEP,
) -> dict[str, Any]:
    """Find articles stuck at status="scored" past the grace period and
    re-dispatch relevance scoring for them. Non-blocking — dispatches via the
    same fire-and-forget/semaphore path as normal auto-scoring and returns
    immediately; it does not wait for scoring to finish."""
    from app.modules.intelligence.application.subscribers import _score_in_background

    cutoff = _utc_now() - _RECOVERY_AFTER
    rows = (
        await session.execute(
            select(Article.id, Article.organization_id)
            .where(Article.status == "scored", Article.updated_at < cutoff)
            .order_by(Article.created_at.asc())
            .limit(limit)
        )
    ).all()

    for article_id, org_id in rows:
        asyncio.create_task(
            _score_in_background(org_id, article_id, session_factory),
            name=f"relevance-recovery-{article_id}",
        )

    return {"redispatched": len(rows)}


async def recover_orphaned_relevance_scoring_startup(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Called once from app lifespan on startup."""
    if not get_settings().RELEVANCE_RECOVERY_ENABLED:
        return
    try:
        async with session_factory() as session:
            result = await recover_orphaned_relevance_scoring(session, session_factory)
            logger.info("Startup relevance orphan recovery: %s", result)
    except Exception:  # noqa: BLE001
        logger.exception("Startup relevance orphan recovery failed")


async def relevance_recovery_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_seconds: int = _SWEEP_INTERVAL_SECONDS,
) -> None:
    """Long-running background sweep — self-heals any orphan, not just ones
    present at startup. No-ops (cheaply) while the feature flag is off."""
    while True:
        await asyncio.sleep(interval_seconds)
        if not get_settings().RELEVANCE_RECOVERY_ENABLED:
            continue
        try:
            async with session_factory() as session:
                result = await recover_orphaned_relevance_scoring(session, session_factory)
                if result["redispatched"]:
                    logger.info("Periodic relevance orphan recovery: %s", result)
        except Exception:  # noqa: BLE001
            logger.exception("Periodic relevance orphan recovery failed")
