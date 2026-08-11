#!/usr/bin/env python3
"""Re-run never-started image batches (one-shot ops script)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main() -> None:
    from sqlalchemy import select

    from app.api.routes.images import _inline_generate_images
    from app.infrastructure.postgres.models.imaging import ImageJob
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.image.application.orphan_recovery import _never_started

    async with async_session_factory() as session:
        jobs = (
            await session.execute(
                select(ImageJob)
                .where(ImageJob.status.in_(("pending", "queued", "running")))
                .order_by(ImageJob.created_at.asc())
            )
        ).scalars().all()
        stuck = [
            j
            for j in jobs
            if (j.generation_metadata_json or {}).get("batch") and _never_started(j)
        ]
        print(f"Found {len(stuck)} never-started batch job(s)")

    for j in stuck:
        meta = j.generation_metadata_json or {}
        count = int(meta.get("requested_count") or 1)
        guidance = meta.get("guidance")
        guidance_s = str(guidance).strip() if guidance else None
        print(f"Generating draft={j.draft_id} batch={j.id} count={count} …")
        await _inline_generate_images(
            j.organization_id, j.draft_id, count, j.id, guidance_s
        )
        print(f"  done batch={j.id}")

    print("Recovery finished")


if __name__ == "__main__":
    asyncio.run(main())
