#!/usr/bin/env python3
"""Recover stuck pending ingest jobs by running them inline.

Use when jobs were dispatched to Dramatiq but no worker is running.
Safe to re-run: skips already-complete/failed jobs.

Usage:
    python scripts/recover_pending_ingest.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import get_settings
from app.infrastructure.postgres.models.jobs import Job
from app.infrastructure.postgres.session import async_session_factory
from app.modules.news.application.run_source import _inline_ingest


async def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    print(f"JOB_BACKEND={settings.JOB_BACKEND}")

    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(Job)
                .where(Job.job_type == "ingest", Job.status == "pending")
                .order_by(Job.created_at.asc())
            )
        ).scalars().all()
        jobs = [
            (j.id, j.organization_id, (j.payload_json or {}).get("source_id"))
            for j in rows
        ]

    if not jobs:
        print("No pending ingest jobs.")
        return

    print(f"Recovering {len(jobs)} pending ingest job(s)...")
    for job_id, org_id, source_id in jobs:
        if not source_id:
            print(f"  skip {job_id}: missing source_id in payload")
            continue
        print(f"  running job={job_id} source={source_id}")
        import uuid

        await _inline_ingest(org_id, uuid.UUID(str(source_id)), job_id)
        print(f"  done job={job_id}")

    print("Recovery complete.")


if __name__ == "__main__":
    asyncio.run(main())
