"""Background-job dispatch for draft/post generation.

Mirrors app/modules/news/application/run_source.py's Job dispatch pattern
(generic Job/JobEvent tables, JOB_BACKEND-aware inline/Dramatiq split) so
draft generation gets the same non-blocking job + poll story as news ingest,
instead of tying up the HTTP request for the whole LLM call. Image generation
predates this generic table and rolled its own ImageJob — draft generation's
output already lives on Draft/DraftVersion, so payload_json/result_json on
the generic Job is enough; no new table needed.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.postgres.models.jobs import Job, JobEvent

logger = get_logger(__name__)


def _backend() -> str:
    return (get_settings().JOB_BACKEND or "inline").strip().lower()


async def _create_job(
    session: AsyncSession, *, org_id: uuid.UUID, job_type: str, payload: dict[str, Any]
) -> Job:
    job = Job(
        organization_id=org_id,
        job_type=job_type,
        status="pending",
        payload_json=payload,
        correlation_id=str(uuid.uuid4()),
    )
    session.add(job)
    await session.flush()
    session.add(JobEvent(job_id=job.id, event_type="created", message=f"{job_type} queued"))
    await session.flush()
    # Commit job row before dispatch so workers / inline tasks can see it.
    await session.commit()
    return job


class DispatchGenerateDraftJob:
    """Queue draft generation from an article, inline or via Dramatiq."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        org_id: uuid.UUID,
        article_id: uuid.UUID,
        content_type: str = "educational",
        force: bool = False,
        origin: str = "manual_news",
    ) -> dict[str, Any]:
        job = await _create_job(
            self._session,
            org_id=org_id,
            job_type="draft_generate",
            payload={
                "article_id": str(article_id),
                "content_type": content_type,
                "force": force,
                "origin": origin,
            },
        )
        if _backend() == "dramatiq":
            from app.workers.draft_generation import run_generate_draft_task

            run_generate_draft_task.send(
                str(org_id), str(article_id), content_type, force, origin, str(job.id)
            )
            logger.info("Dispatched Dramatiq draft generate: job_id=%s", job.id)
        else:
            asyncio.create_task(
                _run_inline_generate(org_id, article_id, content_type, force, origin, job.id),
                name=f"draft-generate-{job.id}",
            )
            logger.info("Dispatched inline draft generate: job_id=%s", job.id)
        return {"job_id": str(job.id), "status": "pending"}


class DispatchRegenerateDraftJob:
    """Queue a draft regenerate (full post or a section), inline or via Dramatiq."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        section: str = "full",
        guidance: str | None = None,
    ) -> dict[str, Any]:
        job = await _create_job(
            self._session,
            org_id=org_id,
            job_type="draft_regenerate",
            payload={"draft_id": str(draft_id), "section": section, "guidance": guidance},
        )
        if _backend() == "dramatiq":
            from app.workers.draft_generation import run_regenerate_draft_task

            run_regenerate_draft_task.send(
                str(org_id), str(draft_id), section, guidance or "", str(job.id)
            )
            logger.info("Dispatched Dramatiq draft regenerate: job_id=%s", job.id)
        else:
            asyncio.create_task(
                _run_inline_regenerate(org_id, draft_id, section, guidance, job.id),
                name=f"draft-regenerate-{job.id}",
            )
            logger.info("Dispatched inline draft regenerate: job_id=%s", job.id)
        return {"job_id": str(job.id), "status": "pending"}


class DispatchFillEducationalJob:
    """Queue the Plan page's educational-gap fill (was a synchronous N-draft loop)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, *, org_id: uuid.UUID, max_generate: int | None = None, ensure_image: bool = True
    ) -> dict[str, Any]:
        job = await _create_job(
            self._session,
            org_id=org_id,
            job_type="plan_fill_educational",
            payload={"max_generate": max_generate, "ensure_image": ensure_image},
        )
        if _backend() == "dramatiq":
            from app.workers.draft_generation import run_fill_educational_task

            run_fill_educational_task.send(str(org_id), max_generate, ensure_image, str(job.id))
            logger.info("Dispatched Dramatiq plan fill-educational: job_id=%s", job.id)
        else:
            asyncio.create_task(
                _run_inline_fill_educational(org_id, max_generate, ensure_image, job.id),
                name=f"plan-fill-educational-{job.id}",
            )
            logger.info("Dispatched inline plan fill-educational: job_id=%s", job.id)
        return {"job_id": str(job.id), "status": "pending"}


class DispatchRegeneratePlanJob:
    """Queue the Plan page's full mix regenerate (educational + Capture gaps)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, *, org_id: uuid.UUID, max_generate: int | None = None) -> dict[str, Any]:
        job = await _create_job(
            self._session,
            org_id=org_id,
            job_type="plan_regenerate",
            payload={"max_generate": max_generate},
        )
        if _backend() == "dramatiq":
            from app.workers.draft_generation import run_regenerate_plan_task

            run_regenerate_plan_task.send(str(org_id), max_generate, str(job.id))
            logger.info("Dispatched Dramatiq plan regenerate: job_id=%s", job.id)
        else:
            asyncio.create_task(
                _run_inline_regenerate_plan(org_id, max_generate, job.id),
                name=f"plan-regenerate-{job.id}",
            )
            logger.info("Dispatched inline plan regenerate: job_id=%s", job.id)
        return {"job_id": str(job.id), "status": "pending"}


# ── Inline (in-process asyncio) runners — mirror run_source.py's _run_inline_ingest ──


async def _run_inline_generate(
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    content_type: str,
    force: bool,
    origin: str,
    job_id: uuid.UUID,
) -> None:
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.ai.application.factory import AIOrchestratorFactory
    from app.modules.content.application.use_cases import GenerateDraftUseCase

    async with async_session_factory() as session:
        try:
            await session.execute(
                sql_update(Job).where(Job.id == job_id).values(
                    status="running", attempts=Job.attempts + 1
                )
            )
            session.add(
                JobEvent(job_id=job_id, event_type="started", message="Draft generation started")
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
        except Exception as exc:  # noqa: BLE001 — recorded on the job, not re-raised to a caller
            logger.exception("Inline draft generation failed: job_id=%s", job_id)
            await _mark_failed(job_id, str(exc))


async def _run_inline_regenerate(
    org_id: uuid.UUID,
    draft_id: uuid.UUID,
    section: str,
    guidance: str | None,
    job_id: uuid.UUID,
) -> None:
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.ai.application.factory import AIOrchestratorFactory
    from app.modules.content.application.use_cases import RegenerateDraftSectionUseCase

    async with async_session_factory() as session:
        try:
            await session.execute(
                sql_update(Job).where(Job.id == job_id).values(
                    status="running", attempts=Job.attempts + 1
                )
            )
            session.add(
                JobEvent(job_id=job_id, event_type="started", message="Draft regenerate started")
            )
            await session.commit()

            use_case = RegenerateDraftSectionUseCase(session, AIOrchestratorFactory.create())
            result = await use_case.execute(
                org_id, draft_id, section=section or "full", guidance=guidance
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inline draft regenerate failed: job_id=%s", job_id)
            await _mark_failed(job_id, str(exc))


async def _run_inline_fill_educational(
    org_id: uuid.UUID, max_generate: int | None, ensure_image: bool, job_id: uuid.UUID
) -> None:
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.content.application.publishing_plan import PublishingPlanService
    from app.modules.content.application.use_cases import GenerateDraftUseCase

    async with async_session_factory() as session:
        try:
            await session.execute(
                sql_update(Job).where(Job.id == job_id).values(
                    status="running", attempts=Job.attempts + 1
                )
            )
            session.add(
                JobEvent(job_id=job_id, event_type="started", message="Fill-educational started")
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inline fill-educational failed: job_id=%s", job_id)
            await _mark_failed(job_id, str(exc))


async def _run_inline_regenerate_plan(
    org_id: uuid.UUID, max_generate: int | None, job_id: uuid.UUID
) -> None:
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.content.application.publishing_plan import PublishingPlanService
    from app.modules.content.application.use_cases import GenerateDraftUseCase

    async with async_session_factory() as session:
        try:
            await session.execute(
                sql_update(Job).where(Job.id == job_id).values(
                    status="running", attempts=Job.attempts + 1
                )
            )
            session.add(
                JobEvent(job_id=job_id, event_type="started", message="Plan regenerate started")
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inline plan regenerate failed: job_id=%s", job_id)
            await _mark_failed(job_id, str(exc))


async def _mark_failed(job_id: uuid.UUID, error: str) -> None:
    """Record failure in a fresh session — the caller's session may be poisoned
    (failed transaction) by whatever exception triggered this call."""
    from app.infrastructure.postgres.session import async_session_factory

    try:
        async with async_session_factory() as session:
            await session.execute(
                sql_update(Job).where(Job.id == job_id).values(status="failed", last_error=error[:500])
            )
            session.add(JobEvent(job_id=job_id, event_type="failed", message=error[:500]))
            await session.commit()
    except Exception:
        logger.exception("Failed to record job failure in DB for job_id=%s", job_id)
