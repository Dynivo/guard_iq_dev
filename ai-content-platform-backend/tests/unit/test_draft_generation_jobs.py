"""Unit tests for draft-generation job dispatch.

Mirrors the generic Job/JobEvent dispatch pattern used by news ingest
(RunSourceUseCase) — draft generate/regenerate and the Plan page's bulk
fill/regenerate now queue a Job row and run in the background instead of
blocking the HTTP request.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.postgres.models.jobs import Job
from app.modules.content.application.generation.jobs import (
    DispatchFillEducationalJob,
    DispatchGenerateDraftJob,
    DispatchRegenerateDraftJob,
    DispatchRegeneratePlanJob,
)


def _fake_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.parametrize(
    "dispatch_cls,kwargs,job_type",
    [
        (
            DispatchGenerateDraftJob,
            {"org_id": uuid.uuid4(), "article_id": uuid.uuid4(), "content_type": "educational"},
            "draft_generate",
        ),
        (
            DispatchRegenerateDraftJob,
            {
                "org_id": uuid.uuid4(),
                "draft_id": uuid.uuid4(),
                "section": "full",
                "guidance": "shorter",
            },
            "draft_regenerate",
        ),
        (
            DispatchFillEducationalJob,
            {"org_id": uuid.uuid4(), "max_generate": 5},
            "plan_fill_educational",
        ),
        (
            DispatchRegeneratePlanJob,
            {"org_id": uuid.uuid4(), "max_generate": 3},
            "plan_regenerate",
        ),
    ],
)
def test_dispatch_creates_job_and_schedules_inline(dispatch_cls, kwargs, job_type) -> None:
    """Each dispatcher creates a pending Job row with the right type/payload and
    schedules an inline asyncio task (JOB_BACKEND=inline is the test default)."""
    session = _fake_session()

    async def _run() -> None:
        # Close the coroutine instead of scheduling it — we're only testing the
        # dispatch/Job-creation half here, not the background runner itself.
        with patch("asyncio.create_task", side_effect=lambda coro, **_: coro.close()) as create_task:
            result = await dispatch_cls(session).execute(**kwargs)
            assert create_task.called

        assert result["status"] == "pending"
        assert "job_id" in result

        job = session.add.call_args_list[0].args[0]
        assert isinstance(job, Job)
        assert job.job_type == job_type
        assert job.status == "pending"
        assert job.organization_id == kwargs["org_id"]
        session.commit.assert_awaited()

    asyncio.run(_run())


def test_dispatch_uses_dramatiq_when_configured() -> None:
    """When JOB_BACKEND=dramatiq, dispatch sends to the actor instead of asyncio."""
    session = _fake_session()

    async def _run() -> None:
        with (
            patch(
                "app.modules.content.application.generation.jobs._backend",
                return_value="dramatiq",
            ),
            patch("app.workers.draft_generation.run_generate_draft_task") as task,
        ):
            result = await DispatchGenerateDraftJob(session).execute(
                org_id=uuid.uuid4(), article_id=uuid.uuid4()
            )
            task.send.assert_called_once()

        assert result["status"] == "pending"

    asyncio.run(_run())


def test_inline_generate_lands_complete_with_result() -> None:
    """The inline background runner marks the Job complete with the draft as result_json."""
    from app.modules.content.application.generation import jobs as jobs_mod

    org_id = uuid.uuid4()
    article_id = uuid.uuid4()
    job_id = uuid.uuid4()
    fake_draft = {"id": str(uuid.uuid4()), "hook": "H", "generated_text": "body"}

    session = _fake_session()

    @asynccontextmanager
    async def _factory():
        yield session

    use_case = MagicMock()
    use_case.execute = AsyncMock(return_value=fake_draft)

    async def _run() -> None:
        with (
            patch(
                "app.infrastructure.postgres.session.async_session_factory",
                return_value=_factory(),
            ),
            patch(
                "app.modules.content.application.use_cases.GenerateDraftUseCase",
                return_value=use_case,
            ),
            patch("app.modules.ai.application.factory.AIOrchestratorFactory.create"),
        ):
            await jobs_mod._run_inline_generate(
                org_id, article_id, "educational", False, "manual_news", job_id
            )

        use_case.execute.assert_awaited_once()
        # status=running then status=complete, result_json=fake_draft
        assert session.execute.await_count == 2
        complete_values = session.execute.await_args.args[0]
        assert complete_values.compile().params["status"] == "complete"
        assert complete_values.compile().params["result_json"] == fake_draft
        session.commit.assert_awaited()

    asyncio.run(_run())


def test_inline_generate_marks_job_failed_on_exception() -> None:
    """A generation error is recorded on the Job instead of propagating uncaught."""
    from app.modules.content.application.generation import jobs as jobs_mod

    org_id = uuid.uuid4()
    article_id = uuid.uuid4()
    job_id = uuid.uuid4()

    session = _fake_session()

    @asynccontextmanager
    async def _factory():
        yield session

    use_case = MagicMock()
    use_case.execute = AsyncMock(side_effect=RuntimeError("boom"))

    async def _run() -> None:
        with (
            # side_effect (not return_value) — _mark_failed opens its own fresh
            # session on top of the one _run_inline_generate already used, so
            # async_session_factory() must be callable more than once.
            patch(
                "app.infrastructure.postgres.session.async_session_factory",
                side_effect=lambda: _factory(),
            ),
            patch(
                "app.modules.content.application.use_cases.GenerateDraftUseCase",
                return_value=use_case,
            ),
            patch("app.modules.ai.application.factory.AIOrchestratorFactory.create"),
        ):
            # Must not raise — failures are recorded on the Job, not the caller.
            await jobs_mod._run_inline_generate(
                org_id, article_id, "educational", False, "manual_news", job_id
            )

        failed_values = session.execute.await_args.args[0]
        assert failed_values.compile().params["status"] == "failed"
        assert "boom" in failed_values.compile().params["last_error"]

    asyncio.run(_run())
