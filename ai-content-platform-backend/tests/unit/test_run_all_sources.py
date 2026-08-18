"""Run-all source dispatch must queue the full catalogue before workers start."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.infrastructure.postgres.models.jobs import Job, JobEvent
from app.modules.news.application.run_source import (
    RunAllSourcesUseCase,
    RunSourceUseCase,
)


async def test_run_all_persists_every_job_before_inline_dispatch() -> None:
    org_id = uuid.uuid4()
    sources = [
        SimpleNamespace(
            id=uuid.uuid4(),
            name=f"Source {index}",
            enabled=True,
            priority=100 - index,
        )
        for index in range(46)
    ]
    session = MagicMock()
    session.add = MagicMock()

    async def assign_job_ids() -> None:
        for call in session.add.call_args_list:
            row = call.args[0]
            if isinstance(row, Job) and row.id is None:
                row.id = uuid.uuid4()

    session.flush = AsyncMock(side_effect=assign_job_ids)
    session.commit = AsyncMock()
    dispatch = AsyncMock()

    with (
        patch(
            "app.modules.news.application.run_source.PgNewsSourceRepository.list_by_org",
            new=AsyncMock(return_value=sources),
        ),
        patch(
            "app.modules.news.application.run_source.get_settings",
            return_value=SimpleNamespace(JOB_BACKEND="inline"),
        ),
        patch.object(RunSourceUseCase, "_dispatch_inline", new=dispatch),
    ):
        result = await RunAllSourcesUseCase(session).execute(org_id)

    assert result["count"] == 46
    assert session.commit.await_count == 1
    assert dispatch.await_count == 46

    added = [call.args[0] for call in session.add.call_args_list]
    jobs = [row for row in added if isinstance(row, Job)]
    events = [row for row in added if isinstance(row, JobEvent)]
    assert len(jobs) == 46
    assert len(events) == 46

    # Dispatch happens after the single commit that makes all 46 rows durable.
    assert all(job.status == "pending" for job in jobs)
