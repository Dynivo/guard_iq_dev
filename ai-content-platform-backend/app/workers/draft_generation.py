"""Dramatiq actors for draft generation — generate, regenerate, plan fill/regenerate.

Mirrors app/workers/ingest.py: each actor spins up its own asyncio event loop
and a loop-local NullPool engine (worker_session_factory), never the
process-global async_engine, because Dramatiq threads each get a fresh
asyncio.run() event loop.
"""

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


@dramatiq.actor(queue_name="content", max_retries=1)
def run_generate_draft_task(
    org_id_str: str,
    article_id_str: str,
    content_type: str,
    force: bool,
    origin: str,
    job_id_str: str,
) -> None:
    asyncio.run(
        _async_generate(org_id_str, article_id_str, content_type, force, origin, job_id_str)
    )


@dramatiq.actor(queue_name="content", max_retries=1)
def run_regenerate_draft_task(
    org_id_str: str, draft_id_str: str, section: str, guidance: str, job_id_str: str
) -> None:
    asyncio.run(_async_regenerate(org_id_str, draft_id_str, section, guidance, job_id_str))


@dramatiq.actor(queue_name="content", max_retries=1)
def run_fill_educational_task(
    org_id_str: str, max_generate: int | None, ensure_image: bool, job_id_str: str
) -> None:
    asyncio.run(_async_fill_educational(org_id_str, max_generate, ensure_image, job_id_str))


@dramatiq.actor(queue_name="content", max_retries=1)
def run_regenerate_plan_task(org_id_str: str, max_generate: int | None, job_id_str: str) -> None:
    asyncio.run(_async_regenerate_plan(org_id_str, max_generate, job_id_str))


async def _mark_job_failed(
    factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, error: str
) -> None:
    """Record failure in a clean session (main session may be poisoned)."""
    from app.infrastructure.postgres.models.jobs import Job, JobEvent

    try:
        async with factory() as session:
            await session.execute(
                sql_update(Job).where(Job.id == job_id).values(status="failed", last_error=error[:500])
            )
            session.add(JobEvent(job_id=job_id, event_type="failed", message=error[:500]))
            await session.commit()
    except Exception:
        logger.exception("Failed to record job failure in DB for job_id=%s", job_id)


async def _async_generate(
    org_id_str: str,
    article_id_str: str,
    content_type: str,
    force: bool,
    origin: str,
    job_id_str: str,
) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.ai.application.factory import AIOrchestratorFactory
    from app.modules.content.application.use_cases import GenerateDraftUseCase

    org_id = uuid.UUID(org_id_str)
    article_id = uuid.UUID(article_id_str)
    job_id = uuid.UUID(job_id_str)

    async with worker_session_factory() as factory:
        try:
            async with factory() as session:
                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="running", attempts=Job.attempts + 1
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id, event_type="started", message="Draft generation started (dramatiq)"
                    )
                )
                await session.commit()

                use_case = GenerateDraftUseCase(session, AIOrchestratorFactory.create())
                result = await use_case.execute(
                    org_id=org_id,
                    article_id=article_id,
                    content_type=content_type,
                    force=force,
                    origin=origin,
                )

                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="complete", result_json=result
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="completed",
                        message="Draft generated",
                        details_json={"draft_id": result.get("id")},
                    )
                )
                await session.commit()
            logger.info("Dramatiq draft generate complete: job_id=%s", job_id)
        except Exception as exc:
            logger.exception("Dramatiq draft generate failed: job_id=%s", job_id)
            await _mark_job_failed(factory, job_id, str(exc))
            raise


async def _async_regenerate(
    org_id_str: str, draft_id_str: str, section: str, guidance: str, job_id_str: str
) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.ai.application.factory import AIOrchestratorFactory
    from app.modules.content.application.use_cases import RegenerateDraftSectionUseCase

    org_id = uuid.UUID(org_id_str)
    draft_id = uuid.UUID(draft_id_str)
    job_id = uuid.UUID(job_id_str)

    async with worker_session_factory() as factory:
        try:
            async with factory() as session:
                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="running", attempts=Job.attempts + 1
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id, event_type="started", message="Draft regenerate started (dramatiq)"
                    )
                )
                await session.commit()

                use_case = RegenerateDraftSectionUseCase(session, AIOrchestratorFactory.create())
                result = await use_case.execute(
                    org_id, draft_id, section=section or "full", guidance=guidance or None
                )

                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="complete", result_json=result
                    )
                )
                session.add(
                    JobEvent(job_id=job_id, event_type="completed", message="Draft regenerated")
                )
                await session.commit()
            logger.info("Dramatiq draft regenerate complete: job_id=%s", job_id)
        except Exception as exc:
            logger.exception("Dramatiq draft regenerate failed: job_id=%s", job_id)
            await _mark_job_failed(factory, job_id, str(exc))
            raise


async def _async_fill_educational(
    org_id_str: str, max_generate: int | None, ensure_image: bool, job_id_str: str
) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.content.application.publishing_plan import PublishingPlanService
    from app.modules.content.application.use_cases import GenerateDraftUseCase

    org_id = uuid.UUID(org_id_str)
    job_id = uuid.UUID(job_id_str)

    async with worker_session_factory() as factory:
        try:
            async with factory() as session:
                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="running", attempts=Job.attempts + 1
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id, event_type="started", message="Fill-educational started (dramatiq)"
                    )
                )
                await session.commit()

                svc = PublishingPlanService(session, generate_uc=GenerateDraftUseCase(session))
                result = await svc.fill_educational(
                    org_id, max_generate=max_generate, ensure_image=ensure_image
                )
                plan = await svc.get_plan(org_id)
                result["plan"] = {
                    "counts": plan["counts"],
                    "gaps": plan["gaps"],
                    "total_count": plan["total_count"],
                    "target": plan["target"],
                    "window": plan["window"],
                    "slots": plan["slots"],
                    "needs_capture": plan.get("needs_capture"),
                }

                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="complete", result_json=result
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="completed",
                        message=result.get("message") or "Fill-educational complete",
                        details_json={"generated": len(result.get("generated") or [])},
                    )
                )
                await session.commit()
            logger.info("Dramatiq fill-educational complete: job_id=%s", job_id)
        except Exception as exc:
            logger.exception("Dramatiq fill-educational failed: job_id=%s", job_id)
            await _mark_job_failed(factory, job_id, str(exc))
            raise


async def _async_regenerate_plan(org_id_str: str, max_generate: int | None, job_id_str: str) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.content.application.publishing_plan import PublishingPlanService
    from app.modules.content.application.use_cases import GenerateDraftUseCase

    org_id = uuid.UUID(org_id_str)
    job_id = uuid.UUID(job_id_str)

    async with worker_session_factory() as factory:
        try:
            async with factory() as session:
                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="running", attempts=Job.attempts + 1
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id, event_type="started", message="Plan regenerate started (dramatiq)"
                    )
                )
                await session.commit()

                svc = PublishingPlanService(session, generate_uc=GenerateDraftUseCase(session))
                result = await svc.regenerate_plan(org_id, max_generate=max_generate)

                await session.execute(
                    sql_update(Job).where(Job.id == job_id).values(
                        status="complete", result_json=result
                    )
                )
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="completed",
                        message=result.get("message") or "Plan regenerate complete",
                        details_json={"generated": len(result.get("generated") or [])},
                    )
                )
                await session.commit()
            logger.info("Dramatiq plan regenerate complete: job_id=%s", job_id)
        except Exception as exc:
            logger.exception("Dramatiq plan regenerate failed: job_id=%s", job_id)
            await _mark_job_failed(factory, job_id, str(exc))
            raise
