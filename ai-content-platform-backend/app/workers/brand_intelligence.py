"""Dramatiq actor for brand intelligence import jobs."""

from __future__ import annotations

import asyncio
import uuid

import dramatiq
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.workers.broker import ensure_broker

logger = get_logger(__name__)
ensure_broker()


@dramatiq.actor(queue_name="brand_import", max_retries=1, min_backoff=15_000)
def run_brand_import_task(
    org_id_str: str,
    import_id_str: str,
    job_id_str: str,
    bi_job_id_str: str,
) -> None:
    asyncio.run(_async_brand_import(org_id_str, import_id_str, job_id_str, bi_job_id_str))


async def _async_brand_import(
    org_id_str: str,
    import_id_str: str,
    job_id_str: str,
    bi_job_id_str: str,
) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.brand_intelligence.application.pipeline import BrandIntelligencePipeline
    from app.modules.brand_intelligence.application.use_cases import BrandIntelligenceUseCases

    org_id = uuid.UUID(org_id_str)
    import_id = uuid.UUID(import_id_str)
    job_id = uuid.UUID(job_id_str)
    bi_job_id = uuid.UUID(bi_job_id_str)
    factory = worker_session_factory()

    async with factory() as session:
        uc = BrandIntelligenceUseCases(session)
        bi_job = await uc.import_jobs.get(org_id, bi_job_id)
        job = await session.get(Job, job_id)
        if not bi_job or not job:
            return
        job.status = "running"
        await session.commit()
        try:
            session_rec = await uc.sessions.load(org_id, "linkedin")
            pipeline = BrandIntelligencePipeline(
                session,
                browser_session_bytes=session_rec.ciphertext if session_rec else None,
            )
            memory = await pipeline.run(org_id=org_id, import_id=import_id, bi_job=bi_job)
            job.status = "completed"
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="completed",
                    message=f"brand_import memory={memory.id}",
                )
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("brand_import_failed", extra={"job_id": job_id_str})
            await _mark_failed(factory, job_id, str(exc))


async def _mark_failed(factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, error: str) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent

    async with factory() as session:
        await session.execute(
            sql_update(Job).where(Job.id == job_id).values(status="failed", last_error=error[:500])
        )
        session.add(JobEvent(job_id=job_id, event_type="failed", message=error[:500]))
        await session.commit()
