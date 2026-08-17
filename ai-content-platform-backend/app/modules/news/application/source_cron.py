"""Periodic cron evaluation for news sources.

Mirrors app/modules/intelligence/application/orphan_recovery.py's pattern: a
long-running asyncio loop started from app lifespan, sweeping the DB on an
interval rather than holding any in-memory "next run" state — so a source's
due-ness is always recomputed from `schedule_cron` + `last_fetched_at`
directly and nothing is lost across a restart, just possibly delayed until
the next sweep.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.postgres.models.jobs import Job
from app.infrastructure.postgres.models.news import NewsSource
from app.modules.news.application.run_source import RunSourceUseCase

logger = get_logger(__name__)

_IN_FLIGHT_STATUSES = ("pending", "running")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_due(schedule_cron: str, last_fetched_at: datetime | None, now: datetime) -> bool:
    """A source is due once `now` has passed the first cron fire time after
    its last successful fetch (or immediately, if it has never run)."""
    if not last_fetched_at:
        return True
    try:
        nxt = croniter(schedule_cron, last_fetched_at).get_next(datetime)
    except (ValueError, KeyError):
        # Malformed cron expression — don't spin retrying it every sweep.
        return False
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    return now >= nxt


async def run_due_sources(session: AsyncSession, *, max_dispatch: int | None = None) -> dict[str, Any]:
    """Find enabled sources whose cron schedule is due and dispatch a run for
    each, skipping any that already have an in-flight ingest job.

    Capped per sweep (default from SOURCE_CRON_MAX_DISPATCH_PER_SWEEP) so a
    fresh install — where every seeded source has no last_fetched_at and is
    therefore due at once — staggers its first runs across several sweeps
    instead of firing all sources simultaneously. Sources not dispatched this
    time remain due and are picked up on a later sweep.
    """
    cap = max_dispatch if max_dispatch is not None else get_settings().SOURCE_CRON_MAX_DISPATCH_PER_SWEEP
    rows = (
        await session.execute(
            select(NewsSource).where(
                NewsSource.enabled.is_(True),
                NewsSource.schedule_cron.isnot(None),
            )
        )
    ).scalars().all()
    if not rows:
        return {"checked": 0, "dispatched": 0}

    in_flight_rows = (
        await session.execute(
            select(Job.payload_json).where(
                Job.job_type == "ingest",
                Job.status.in_(_IN_FLIGHT_STATUSES),
            )
        )
    ).all()
    in_flight_source_ids = {
        str(payload.get("source_id"))
        for (payload,) in in_flight_rows
        if isinstance(payload, dict) and payload.get("source_id")
    }

    now = _utc_now()
    dispatched = 0
    runner = RunSourceUseCase(session)
    for source in rows:
        if cap > 0 and dispatched >= cap:
            break
        if not source.schedule_cron or not source.schedule_cron.strip():
            continue
        if str(source.id) in in_flight_source_ids:
            continue
        if not _is_due(source.schedule_cron, source.last_fetched_at, now):
            continue
        try:
            await runner.execute(org_id=source.organization_id, source_id=source.id)
            dispatched += 1
        except Exception:  # noqa: BLE001
            logger.exception("Cron dispatch failed for source_id=%s", source.id)

    return {"checked": len(rows), "dispatched": dispatched}


async def source_cron_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_seconds: int | None = None,
) -> None:
    """Long-running background sweep — started once from app lifespan."""
    interval = interval_seconds or get_settings().SOURCE_CRON_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(interval)
        if not get_settings().SOURCE_CRON_ENABLED:
            continue
        try:
            async with session_factory() as session:
                result = await run_due_sources(session)
                if result["dispatched"]:
                    logger.info("Source cron sweep: %s", result)
        except Exception:  # noqa: BLE001
            logger.exception("Source cron sweep failed")
