"""Recover orphaned image batch jobs that never left ``pending`` / ``queued``."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.imaging import ImageJob
from app.modules.image.application.queue_generation import (
    is_inflight,
    schedule_image_job,
    set_draft_image_gen,
)

logger = get_logger(__name__)

_ACTIVE = frozenset(
    {"pending", "running", "queued", "generating", "upscaling", "quality_check", "typography"}
)
# Jobs stuck in queued/pending longer than this are re-dispatched (worker died / race).
_REDISPATCH_AFTER = timedelta(seconds=45)
# Jobs that were running but never finished.
_FAIL_RUNNING_AFTER = timedelta(minutes=20)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_age(job: ImageJob) -> timedelta:
    created = job.created_at
    if created is None:
        return timedelta(0)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return _utc_now() - created


def _is_batch_job(job: ImageJob) -> bool:
    meta = job.generation_metadata_json or {}
    return bool(meta.get("batch") or meta.get("async"))


def _never_started(job: ImageJob) -> bool:
    meta = job.generation_metadata_json or {}
    phase = str(meta.get("phase") or "")
    return job.status in {"pending", "queued"} and phase in {"", "queued"}


async def recover_orphaned_image_batches(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Re-dispatch never-started batches; fail long-running stuck workers.

    Never-started jobs (phase still ``queued``) are always re-dispatched — even if
    older than the running timeout — so they are not wrongly marked failed.
    """
    jobs = (
        await session.execute(
            select(ImageJob)
            .where(ImageJob.status.in_(tuple(_ACTIVE)))
            .order_by(ImageJob.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    redispatched = 0
    failed = 0
    for job in jobs:
        if not _is_batch_job(job):
            continue
        if is_inflight(job.id):
            continue
        age = _job_age(job)
        meta = dict(job.generation_metadata_json or {})
        count = int(meta.get("requested_count") or 1)
        guidance = meta.get("guidance")
        guidance_s = str(guidance).strip() if guidance else None
        draft = await session.get(Draft, job.draft_id) if job.draft_id else None

        # Prefer re-dispatch for anything that never left the queue.
        if _never_started(job) and age >= _REDISPATCH_AFTER:
            logger.info(
                "Recovering never-started image batch job_id=%s draft_id=%s age_s=%.0f",
                job.id,
                job.draft_id,
                age.total_seconds(),
            )
            meta["phase"] = "queued"
            meta["recovered_at"] = _utc_now().isoformat()
            meta["recovery"] = "redispatch_never_started"
            job.generation_metadata_json = meta
            job.status = "pending"
            if draft is not None:
                set_draft_image_gen(
                    draft, status="running", batch_job_id=job.id, count=count
                )
            schedule_image_job(
                job.organization_id,
                job.draft_id,
                count,
                job.id,
                guidance_s,
            )
            redispatched += 1
            continue

        # Only fail jobs that actually started and hung.
        if age > _FAIL_RUNNING_AFTER and not _never_started(job):
            job.status = "failed"
            job.error_message = (job.error_message or "Timed out after 20 minutes")[:1000]
            meta["phase"] = "failed"
            meta["stale"] = True
            job.generation_metadata_json = meta
            if draft is not None:
                set_draft_image_gen(
                    draft, status="failed", batch_job_id=job.id, error=job.error_message
                )
            failed += 1

    await session.flush()
    return {"redispatched": redispatched, "failed": failed, "scanned": len(jobs)}


async def recover_orphaned_image_batches_startup(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Called from app lifespan — recover leftovers after uvicorn reload."""
    try:
        # Ensure image runner is registered (import side-effect).
        from app.api.routes import images as _images  # noqa: F401

        async with session_factory() as session:
            result = await recover_orphaned_image_batches(session)
            await session.commit()
            logger.info("Startup image orphan recovery: %s", result)
    except Exception:  # noqa: BLE001
        logger.exception("Startup image orphan recovery failed")
