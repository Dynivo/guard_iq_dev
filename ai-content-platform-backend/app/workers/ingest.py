"""Dramatiq actor for news source ingest.

Runs the IngestWorkflow inside a synchronous Dramatiq actor by
spinning up an asyncio event loop per invocation.

Uses a loop-local NullPool engine — never the process-global async_engine —
because Dramatiq threads each get a fresh asyncio.run() event loop.
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


@dramatiq.actor(queue_name="ingest", max_retries=2, min_backoff=10_000)
def run_ingest_task(org_id_str: str, source_id_str: str, job_id_str: str) -> None:
    """Dramatiq entry point — wraps async ingest in a sync actor."""
    asyncio.run(_async_ingest(org_id_str, source_id_str, job_id_str))


async def _mark_job_failed(
    factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    error: str,
) -> None:
    """Record failure in a clean session (main session may be poisoned)."""
    from app.infrastructure.postgres.models.jobs import Job, JobEvent

    try:
        async with factory() as session:
            await session.execute(
                sql_update(Job)
                .where(Job.id == job_id)
                .values(status="failed", last_error=error[:500])
            )
            session.add(
                JobEvent(job_id=job_id, event_type="failed", message=error[:500])
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record job failure in DB for job_id=%s", job_id)


async def _async_ingest(org_id_str: str, source_id_str: str, job_id_str: str) -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.news.application.ingest_workflow import IngestWorkflow
    from app.modules.news.infrastructure.repositories import (
        PgArticleRepository,
        PgDeduplicator,
        PgNewsSourceRepository,
    )

    org_id = uuid.UUID(org_id_str)
    source_id = uuid.UUID(source_id_str)
    job_id = uuid.UUID(job_id_str)

    async with worker_session_factory() as factory:
        try:
            async with factory() as session:
                await session.execute(
                    sql_update(Job)
                    .where(Job.id == job_id)
                    .values(status="running", attempts=Job.attempts + 1)
                )
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="started",
                        message="Ingest started (dramatiq)",
                    )
                )
                await session.commit()

                source_repo = PgNewsSourceRepository(session)
                article_repo = PgArticleRepository(session)
                dedup = PgDeduplicator(session)
                workflow = IngestWorkflow(source_repo, article_repo, dedup)
                result = await workflow.execute(org_id, source_id)

                await session.execute(
                    sql_update(Job)
                    .where(Job.id == job_id)
                    .values(status="complete", result_json=result)
                )
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="completed",
                        message=f"Saved {result['saved']}, {result['duplicates']} dups",
                        details_json=result,
                    )
                )
                await session.commit()

            article_ids = list(result.get("article_ids") or [])

            # Record that new articles are waiting for a user-commanded batch.
            from app.modules.news.application.post_ingest import notify_articles_imported

            await notify_articles_imported(
                org_id=org_id,
                source_id=source_id,
                article_ids=article_ids,
            )

            logger.info("Dramatiq ingest complete: job_id=%s result=%s", job_id, result)

        except Exception as exc:
            logger.exception("Dramatiq ingest failed: job_id=%s", job_id)
            await _mark_job_failed(factory, job_id, str(exc))
            raise
