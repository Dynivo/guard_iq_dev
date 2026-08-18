"""Durable, command-driven relevance-screening batches.

Each user command claims at most 100 articles by moving them to the durable
``screening`` status before any LLM work begins.  A persistent Job records the
claimed article IDs and progress, which lets the app resume an interrupted
batch after a restart without claiming the same articles twice.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Literal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.constants import ArticleStatus
from app.core.logging import get_logger
from app.infrastructure.postgres.models.identity import Organization
from app.infrastructure.postgres.models.intelligence import RelevanceScore
from app.infrastructure.postgres.models.jobs import Job, JobEvent
from app.infrastructure.postgres.models.news import Article, NewsSource

logger = get_logger(__name__)

ScreeningMode = Literal["unscored", "relevant"]

BATCH_SIZE = 100
SCREENING_CONCURRENCY = 5
_JOB_TYPES = ("relevance_screen_batch", "relevance_rescore_batch")
_ACTIVE_STATUSES = ("pending", "running")
_UNSCORED_STATUSES = (
    ArticleStatus.RAW,
    ArticleStatus.NORMALIZED,
    ArticleStatus.SCORED,
)

# Prevent startup recovery and a route handler in the same process from
# scheduling the same durable job twice.
_scheduled_job_ids: set[uuid.UUID] = set()


def _job_type(mode: ScreeningMode) -> str:
    return "relevance_rescore_batch" if mode == "relevant" else "relevance_screen_batch"


def _job_to_dict(job: Job | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": str(job.id),
        "type": job.job_type,
        "status": job.status,
        "payload": job.payload_json or {},
        "result": job.result_json or {},
        "error_message": job.last_error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


class StartScreeningBatchUseCase:
    """Claim and persist one user-commanded screening batch."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        org_id: uuid.UUID,
        *,
        mode: ScreeningMode,
        batch_size: int = BATCH_SIZE,
    ) -> dict[str, Any]:
        size = max(1, min(int(batch_size), BATCH_SIZE))

        # Lock the org row so two near-simultaneous clicks cannot both observe
        # "no active batch" and claim different sets.  The lock is released by
        # the explicit commit in the route before the background task starts.
        await self._session.execute(
            select(Organization.id)
            .where(Organization.id == org_id)
            .with_for_update()
        )

        active = (
            await self._session.execute(
                select(Job)
                .where(
                    Job.organization_id == org_id,
                    Job.job_type.in_(_JOB_TYPES),
                    Job.status.in_(_ACTIVE_STATUSES),
                )
                .order_by(Job.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if active is not None:
            return {
                "job": _job_to_dict(active),
                "job_id": str(active.id),
                "queued": 0,
                "already_active": True,
            }

        rows = await self._select_articles(org_id, mode=mode, limit=size)
        if not rows:
            return {
                "job": None,
                "job_id": None,
                "queued": 0,
                "already_active": False,
            }

        article_ids = [row[0] for row in rows]
        originals = {str(article_id): str(status) for article_id, status in rows}
        await self._session.execute(
            update(Article)
            .where(
                Article.organization_id == org_id,
                Article.id.in_(article_ids),
            )
            .values(status=ArticleStatus.SCREENING)
        )

        waiting = await self._pending_count(org_id) if mode == "unscored" else 0
        job = Job(
            organization_id=org_id,
            job_type=_job_type(mode),
            status="pending",
            payload_json={
                "mode": mode,
                "batch_size": len(article_ids),
                "article_ids": [str(article_id) for article_id in article_ids],
                "original_statuses": originals,
            },
            result_json={
                "total": len(article_ids),
                "completed": 0,
                "succeeded": 0,
                "failed": 0,
                "waiting": waiting,
            },
        )
        self._session.add(job)
        await self._session.flush()
        self._session.add(
            JobEvent(
                job_id=job.id,
                event_type="queued",
                message=(
                    f"Queued {len(article_ids)} relevant articles for rescoring"
                    if mode == "relevant"
                    else f"Queued {len(article_ids)} unscored articles for screening"
                ),
                details_json={"mode": mode, "total": len(article_ids), "waiting": waiting},
            )
        )
        return {
            "job": _job_to_dict(job),
            "job_id": str(job.id),
            "queued": len(article_ids),
            "waiting": waiting,
            "already_active": False,
        }

    async def _select_articles(
        self,
        org_id: uuid.UUID,
        *,
        mode: ScreeningMode,
        limit: int,
    ) -> list[tuple[uuid.UUID, str]]:
        if mode == "relevant":
            last_scored_at = (
                select(func.max(RelevanceScore.created_at))
                .where(RelevanceScore.article_id == Article.id)
                .correlate(Article)
                .scalar_subquery()
            )
            stmt = (
                select(Article.id, Article.status)
                .where(
                    Article.organization_id == org_id,
                    Article.status == ArticleStatus.RELEVANT,
                )
                # Least-recently scored first means repeated commands rotate
                # through the relevant set instead of rescoring the same 100.
                .order_by(
                    last_scored_at.asc().nullsfirst(),
                    func.coalesce(Article.published_at, Article.created_at).desc(),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        else:
            stmt = (
                select(Article.id, Article.status)
                .join(NewsSource, NewsSource.id == Article.source_id)
                .where(
                    Article.organization_id == org_id,
                    Article.status.in_(_UNSCORED_STATUSES),
                )
                # Honour the editorial source list first, then take the
                # freshest stories within each priority tier. This keeps the
                # original NCSC/MSRC/The Hacker News sources at the front of
                # each commanded batch instead of letting lower-value feeds
                # displace them solely because they published minutes later.
                .order_by(
                    NewsSource.priority.desc().nullslast(),
                    func.coalesce(Article.published_at, Article.created_at).desc(),
                    Article.created_at.desc(),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        return list((await self._session.execute(stmt)).all())

    async def _pending_count(self, org_id: uuid.UUID) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count(Article.id)).where(
                        Article.organization_id == org_id,
                        Article.status.in_(_UNSCORED_STATUSES),
                    )
                )
            ).scalar_one()
        )


async def get_screening_status(session: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Return the active/latest batch plus live unscored queue depth."""
    active = (
        await session.execute(
            select(Job)
            .where(
                Job.organization_id == org_id,
                Job.job_type.in_(_JOB_TYPES),
                Job.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    latest = active
    if latest is None:
        latest = (
            await session.execute(
                select(Job)
                .where(
                    Job.organization_id == org_id,
                    Job.job_type.in_(_JOB_TYPES),
                )
                .order_by(Job.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    counts = dict(
        (
            await session.execute(
                select(Article.status, func.count(Article.id))
                .where(Article.organization_id == org_id)
                .group_by(Article.status)
            )
        ).all()
    )
    pending = sum(int(counts.get(status, 0)) for status in _UNSCORED_STATUSES)
    return {
        "active": active is not None,
        "job": _job_to_dict(latest),
        "pending": pending,
        "screening": int(counts.get(ArticleStatus.SCREENING, 0)),
        "relevant": int(counts.get(ArticleStatus.RELEVANT, 0)),
        "irrelevant": int(counts.get(ArticleStatus.IRRELEVANT, 0)),
        "batch_size": BATCH_SIZE,
        "concurrency": SCREENING_CONCURRENCY,
    }


def schedule_screening_batch(
    job_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Schedule a durable batch once in this process."""
    if job_id in _scheduled_job_ids:
        return False
    _scheduled_job_ids.add(job_id)
    task = asyncio.create_task(
        run_screening_batch(job_id, session_factory),
        name=f"relevance-screen-batch-{job_id}",
    )

    def _done(_: asyncio.Task) -> None:
        _scheduled_job_ids.discard(job_id)

    task.add_done_callback(_done)
    return True


async def _screen_one(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    original_status: str,
    semaphore: asyncio.Semaphore,
) -> tuple[bool, str | None]:
    async with semaphore:
        try:
            async with session_factory() as session:
                from app.modules.ai.application.factory import AIOrchestratorFactory
                from app.modules.intelligence.application.workflow import IntelligenceWorkflow

                workflow = IntelligenceWorkflow(session, AIOrchestratorFactory.create())
                await workflow.run(org_id=org_id, article_id=article_id)
                await session.commit()
            return True, None
        except Exception as exc:  # noqa: BLE001
            logger.exception("screening_batch.article_failed article=%s", article_id)
            # Put failures back into their original queue/category so another
            # explicit command can retry them; never leave them stuck screening.
            try:
                async with session_factory() as session:
                    await session.execute(
                        update(Article)
                        .where(
                            Article.id == article_id,
                            Article.organization_id == org_id,
                            Article.status == ArticleStatus.SCREENING,
                        )
                        .values(status=original_status)
                    )
                    await session.commit()
            except Exception:  # noqa: BLE001
                logger.exception("screening_batch.restore_failed article=%s", article_id)
            return False, str(exc)[:500]


async def _update_job_progress(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    result: dict[str, Any],
) -> None:
    async with session_factory() as session:
        await session.execute(
            update(Job).where(Job.id == job_id).values(result_json=dict(result))
        )
        await session.commit()


async def _reconcile_batch_duplicates(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    org_id: uuid.UUID,
    article_ids: list[uuid.UUID],
) -> int:
    """Keep the strongest of locally similar recommendations in one batch."""
    from app.modules.intelligence.application.workflow import _same_story

    async with session_factory() as session:
        articles = list(
            (
                await session.execute(
                    select(Article).where(
                        Article.organization_id == org_id,
                        Article.id.in_(article_ids),
                        Article.status == ArticleStatus.RELEVANT,
                    )
                )
            ).scalars().all()
        )
        articles.sort(
            key=lambda article: (
                int((article.score_json or {}).get("ai_relevance") or 0),
                article.published_at or article.created_at,
            ),
            reverse=True,
        )
        kept_titles: list[str] = []
        downgraded = 0
        for article in articles:
            if not any(_same_story(article.title, kept) for kept in kept_titles):
                kept_titles.append(article.title)
                continue
            score = dict(article.score_json or {})
            score["decision"] = "rejected"
            score["article_type"] = "reject"
            score["ai_relevance"] = min(int(score.get("ai_relevance") or 3), 3)
            score["relevance"] = min(int(score.get("relevance") or 3), 3)
            score["reason"] = (
                f"{score.get('reason') or 'In-scope story'}; downgraded because a stronger "
                "version of the same story was recommended in this batch."
            )
            article.status = ArticleStatus.IRRELEVANT
            article.score_json = score
            downgraded += 1
        if downgraded:
            await session.commit()
        return downgraded


async def run_screening_batch(
    job_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Run or resume one persisted batch, then stop until the next command."""
    try:
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status not in _ACTIVE_STATUSES:
                return
            payload = dict(job.payload_json or {})
            mode = str(payload.get("mode") or "unscored")
            org_id = job.organization_id
            all_ids = [uuid.UUID(str(value)) for value in payload.get("article_ids") or []]
            originals = {
                str(key): str(value)
                for key, value in (payload.get("original_statuses") or {}).items()
            }
            remaining_ids = list(
                (
                    await session.execute(
                        select(Article.id).where(
                            Article.organization_id == org_id,
                            Article.id.in_(all_ids),
                            Article.status == ArticleStatus.SCREENING,
                        )
                    )
                ).scalars().all()
            )
            total = len(all_ids)
            completed_before = max(0, total - len(remaining_ids))
            previous = dict(job.result_json or {})
            failed_before = min(int(previous.get("failed") or 0), completed_before)
            result = {
                "total": total,
                "completed": completed_before,
                "succeeded": max(0, completed_before - failed_before),
                "failed": failed_before,
                "waiting": int(previous.get("waiting") or 0),
            }
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="running",
                    attempts=Job.attempts + 1,
                    last_error=None,
                    result_json=result,
                )
            )
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type="started" if completed_before == 0 else "resumed",
                    message=f"Screening batch {mode} started",
                    details_json={"remaining": len(remaining_ids), "total": total},
                )
            )
            await session.commit()

        semaphore = asyncio.Semaphore(SCREENING_CONCURRENCY)
        tasks = [
            asyncio.create_task(
                _screen_one(
                    session_factory,
                    org_id=org_id,
                    article_id=article_id,
                    original_status=originals.get(
                        str(article_id),
                        ArticleStatus.RELEVANT if mode == "relevant" else ArticleStatus.SCORED,
                    ),
                    semaphore=semaphore,
                )
            )
            for article_id in remaining_ids
        ]
        for completed_task in asyncio.as_completed(tasks):
            ok, error = await completed_task
            result["completed"] = int(result["completed"]) + 1
            key = "succeeded" if ok else "failed"
            result[key] = int(result[key]) + 1
            if error:
                result["last_item_error"] = error
            await _update_job_progress(session_factory, job_id, result)

        result["duplicate_rejections"] = await _reconcile_batch_duplicates(
            session_factory,
            org_id=org_id,
            article_ids=all_ids,
        )

        async with session_factory() as session:
            pending = int(
                (
                    await session.execute(
                        select(func.count(Article.id)).where(
                            Article.organization_id == org_id,
                            Article.status.in_(_UNSCORED_STATUSES),
                        )
                    )
                ).scalar_one()
            )
            result["waiting"] = pending
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="complete", result_json=result, last_error=None)
            )
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type="completed",
                    message=(
                        f"Screened {result['succeeded']}/{result['total']} articles; "
                        f"{result['failed']} failed"
                    ),
                    details_json=result,
                )
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("screening_batch.failed job=%s", job_id)
        try:
            async with session_factory() as session:
                job = await session.get(Job, job_id)
                if job is not None:
                    payload = dict(job.payload_json or {})
                    originals = payload.get("original_statuses") or {}
                    for article_id_raw in payload.get("article_ids") or []:
                        article_id = uuid.UUID(str(article_id_raw))
                        await session.execute(
                            update(Article)
                            .where(
                                Article.id == article_id,
                                Article.status == ArticleStatus.SCREENING,
                            )
                            .values(
                                status=str(originals.get(str(article_id)) or ArticleStatus.SCORED)
                            )
                        )
                    job.status = "failed"
                    job.last_error = str(exc)[:1000]
                    session.add(
                        JobEvent(
                            job_id=job_id,
                            event_type="failed",
                            message=str(exc)[:500],
                        )
                    )
                    await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("screening_batch.mark_failed_failed job=%s", job_id)


async def resume_screening_batches_startup(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Resume batches that were pending/running when the app stopped."""
    try:
        async with session_factory() as session:
            job_ids = list(
                (
                    await session.execute(
                        select(Job.id)
                        .where(
                            Job.job_type.in_(_JOB_TYPES),
                            Job.status.in_(_ACTIVE_STATUSES),
                        )
                        .order_by(Job.created_at.asc())
                    )
                ).scalars().all()
            )
        for pending_job_id in job_ids:
            schedule_screening_batch(pending_job_id, session_factory)
        if job_ids:
            logger.info("Resumed %d relevance screening batches", len(job_ids))
    except Exception:  # noqa: BLE001
        logger.exception("Failed to resume relevance screening batches")
