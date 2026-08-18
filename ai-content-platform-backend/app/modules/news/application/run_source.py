"""RunSourceUseCase — triggers ingest for a source, inline or via Dramatiq.

Checks settings.JOB_BACKEND to decide dispatch strategy.  Returns a job_id
so the caller can poll status.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.infrastructure.postgres.models.jobs import Job, JobEvent
from app.modules.news.application.ingest_workflow import IngestWorkflow
from app.modules.news.infrastructure.repositories import (
    PgArticleRepository,
    PgDeduplicator,
    PgNewsSourceRepository,
)

logger = get_logger(__name__)

# Inline ingest holds one DB connection per job for the whole fetch+save
# duration. Cap how many run at once, process-wide, well under the
# SQLAlchemy pool ceiling (default pool_size=5 + max_overflow=10 = 15) —
# this bounds a single `run-all` on a large catalog *and* any overlap
# between multiple run-all/run calls (double-click, retries, two tabs),
# which a per-call batch split alone would not.
_DEFAULT_PARALLEL_LIMIT = 5
_inline_semaphore = asyncio.Semaphore(_DEFAULT_PARALLEL_LIMIT)


class RunAllSourcesUseCase:
    """Dispatch ingest for every enabled source in the org.

    Sources are ordered by ``priority`` so the ones most likely to matter
    start first. Actual DB-connection usage is throttled process-wide by
    ``_inline_semaphore``, so lower-priority sources effectively queue and
    run as earlier ones finish, keeping concurrent inline ingest well under
    the DB pool limit regardless of catalog size.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID) -> dict:
        source_repo = PgNewsSourceRepository(self._session)
        sources = await source_repo.list_by_org(org_id)
        enabled = [s for s in sources if s.enabled]
        enabled.sort(key=lambda s: (s.priority or 0), reverse=True)

        # Persist the complete run-all queue before any inline worker can
        # acquire and hold a pooled DB connection. Dispatching each job as it
        # is created can starve this request after the first five workers,
        # leaving the rest of the source catalogue with no Job row at all.
        queued = []
        for source in enabled:
            job = Job(
                organization_id=org_id,
                job_type="ingest",
                status="pending",
                payload_json={"source_id": str(source.id)},
                correlation_id=str(uuid.uuid4()),
            )
            self._session.add(job)
            queued.append((source, job))

        await self._session.flush()
        for source, job in queued:
            self._session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="created",
                    message=f"Ingest job created for source '{source.name}'",
                )
            )
        await self._session.commit()

        runner = RunSourceUseCase(self._session)
        backend = (get_settings().JOB_BACKEND or "inline").strip().lower()
        jobs: list[dict] = []
        for source, job in queued:
            if backend == "dramatiq":
                await runner._dispatch_dramatiq(str(org_id), str(source.id), str(job.id))
            else:
                await runner._dispatch_inline(org_id, source.id, job.id)
            jobs.append(
                {
                    "job_id": str(job.id),
                    "status": "pending",
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "backend": backend,
                }
            )
        return {
            "jobs": jobs,
            "count": len(jobs),
            "skipped_disabled": len(sources) - len(enabled),
        }


class RunSourceUseCase:
    """Dispatch an ingest job for a news source."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, source_id: uuid.UUID) -> dict:
        source_repo = PgNewsSourceRepository(self._session)
        source = await source_repo.get_by_id(source_id, org_id)
        if source is None:
            raise NotFoundError("NewsSource", str(source_id))

        job = Job(
            organization_id=org_id,
            job_type="ingest",
            status="pending",
            payload_json={"source_id": str(source_id)},
            correlation_id=str(uuid.uuid4()),
        )
        self._session.add(job)
        await self._session.flush()

        self._session.add(JobEvent(
            job_id=job.id,
            event_type="created",
            message=f"Ingest job created for source '{source.name}'",
        ))
        await self._session.flush()

        settings = get_settings()
        # Commit job row before dispatch so workers / inline tasks can see it.
        await self._session.commit()

        backend = (settings.JOB_BACKEND or "inline").strip().lower()
        if backend == "dramatiq":
            await self._dispatch_dramatiq(str(org_id), str(source_id), str(job.id))
        else:
            await self._dispatch_inline(org_id, source_id, job.id)

        return {
            "job_id": str(job.id),
            "status": "pending",
            "source_id": str(source_id),
            "source_name": source.name,
            "backend": backend,
        }

    async def _dispatch_dramatiq(
        self, org_id: str, source_id: str, job_id: str
    ) -> None:
        """Send the ingest task to Dramatiq (imports lazily to avoid broker init at import)."""
        from app.workers.ingest import run_ingest_task
        run_ingest_task.send(org_id, source_id, job_id)
        logger.info("Dispatched Dramatiq ingest: job_id=%s source_id=%s", job_id, source_id)

    async def _dispatch_inline(
        self, org_id: uuid.UUID, source_id: uuid.UUID, job_id: uuid.UUID
    ) -> None:
        """Run ingest as a background asyncio task in the same process."""
        asyncio.create_task(
            _inline_ingest(org_id, source_id, job_id),
            name=f"ingest-{job_id}",
        )
        logger.info("Dispatched inline ingest: job_id=%s source_id=%s", job_id, source_id)


async def _inline_ingest(
    org_id: uuid.UUID, source_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    """Execute the ingest workflow in a standalone session (background task).

    Gated by ``_inline_semaphore`` so only a few of these hold a pooled DB
    connection at once, no matter how many were dispatched or how many
    separate dispatch calls (run-all, run, overlapping calls) triggered them.
    """
    async with _inline_semaphore:
        await _run_inline_ingest(org_id, source_id, job_id)


async def _run_inline_ingest(
    org_id: uuid.UUID, source_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.infrastructure.postgres.session import async_session_factory

    async with async_session_factory() as session:
        try:
            from sqlalchemy import update as sql_update
            stmt = sql_update(Job).where(Job.id == job_id).values(
                status="running", attempts=Job.attempts + 1
            )
            await session.execute(stmt)
            session.add(JobEvent(
                job_id=job_id, event_type="started", message="Ingest started (inline)"
            ))
            await session.commit()

            source_repo = PgNewsSourceRepository(session)
            article_repo = PgArticleRepository(session)
            dedup = PgDeduplicator(session)
            workflow = IngestWorkflow(source_repo, article_repo, dedup)
            result = await workflow.execute(org_id, source_id)

            stmt = sql_update(Job).where(Job.id == job_id).values(
                status="complete", result_json=result
            )
            await session.execute(stmt)
            session.add(JobEvent(
                job_id=job_id,
                event_type="completed",
                message=f"Saved {result['saved']} articles, {result['duplicates']} duplicates",
                details_json=result,
            ))
            await session.commit()

            # After commit: notify subscribers (auto-relevance, analytics)
            from app.modules.news.application.post_ingest import notify_articles_imported

            await notify_articles_imported(
                org_id=org_id,
                source_id=source_id,
                article_ids=list(result.get("article_ids") or []),
            )

        except Exception as exc:
            logger.exception("Inline ingest failed: job_id=%s", job_id)
            try:
                from sqlalchemy import update as sql_update
                stmt = sql_update(Job).where(Job.id == job_id).values(
                    status="failed", last_error=str(exc)[:500]
                )
                await session.execute(stmt)
                session.add(JobEvent(
                    job_id=job_id, event_type="failed", message=str(exc)[:500]
                ))
                await session.commit()
            except Exception:
                logger.exception("Failed to update job status after ingest failure")
