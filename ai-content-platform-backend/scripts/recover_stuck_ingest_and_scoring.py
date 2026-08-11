"""Recover stuck ingest jobs + finish AI scoring for articles left as 'scored'.

Fixes the common local failure mode:
  - Dramatiq ingest crashed on asyncpg (job stays pending)
  - Articles stay status=scored ("Scoring…" in UI) because worker never ran relevance

Usage:
  PYTHONPATH=. .venv/bin/python scripts/recover_stuck_ingest_and_scoring.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update as sql_update


async def main() -> None:
    from app.infrastructure.postgres.models.jobs import Job, JobEvent
    from app.infrastructure.postgres.models.news import Article
    from app.infrastructure.postgres.worker_session import worker_session_factory
    from app.modules.ai.application.factory import AIOrchestratorFactory
    from app.modules.intelligence.application.workflow import IntelligenceWorkflow
    from app.modules.news.application.ingest_workflow import IngestWorkflow
    from app.modules.news.infrastructure.repositories import (
        PgArticleRepository,
        PgDeduplicator,
        PgNewsSourceRepository,
    )

    async with worker_session_factory() as factory:
        # --- 1) Stuck ingest jobs ---
        async with factory() as session:
            stuck = (
                await session.execute(
                    select(Job)
                    .where(
                        Job.job_type == "ingest",
                        Job.status.in_(("pending", "running", "queued")),
                    )
                    .order_by(Job.created_at.asc())
                )
            ).scalars().all()
            jobs = [
                (
                    j.id,
                    j.organization_id,
                    (j.payload_json or {}).get("source_id"),
                    j.status,
                )
                for j in stuck
            ]

        if not jobs:
            print("No stuck ingest jobs.")
        else:
            print(f"Recovering {len(jobs)} stuck ingest job(s)...")
            for job_id, org_id, source_id, status in jobs:
                if not source_id or not org_id:
                    print(f"  fail {job_id}: missing org/source (was {status})")
                    async with factory() as session:
                        await session.execute(
                            sql_update(Job)
                            .where(Job.id == job_id)
                            .values(
                                status="failed",
                                last_error="Recovered: missing source_id/org on stuck job",
                            )
                        )
                        session.add(
                            JobEvent(
                                job_id=job_id,
                                event_type="failed",
                                message="Recovered: missing payload",
                            )
                        )
                        await session.commit()
                    continue

                print(f"  re-run job={job_id} source={source_id} (was {status})")
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
                                message="Recovered stuck ingest (inline)",
                            )
                        )
                        await session.commit()

                        workflow = IngestWorkflow(
                            PgNewsSourceRepository(session),
                            PgArticleRepository(session),
                            PgDeduplicator(session),
                        )
                        result = await workflow.execute(
                            org_id, uuid.UUID(str(source_id))
                        )
                        await session.execute(
                            sql_update(Job)
                            .where(Job.id == job_id)
                            .values(status="complete", result_json=result)
                        )
                        session.add(
                            JobEvent(
                                job_id=job_id,
                                event_type="completed",
                                message=(
                                    f"Recovered: saved {result.get('saved')}, "
                                    f"{result.get('duplicates')} dups"
                                ),
                                details_json=result,
                            )
                        )
                        await session.commit()
                        article_ids = list(result.get("article_ids") or [])
                    print(f"  done job={job_id} saved={len(article_ids)}")
                except Exception as exc:
                    print(f"  FAILED job={job_id}: {exc}")
                    async with factory() as session:
                        await session.execute(
                            sql_update(Job)
                            .where(Job.id == job_id)
                            .values(status="failed", last_error=str(exc)[:500])
                        )
                        session.add(
                            JobEvent(
                                job_id=job_id,
                                event_type="failed",
                                message=str(exc)[:500],
                            )
                        )
                        await session.commit()

        # --- 2) Articles stuck in keyword-scored (awaiting AI) ---
        async with factory() as session:
            rows = (
                await session.execute(
                    select(Article.id, Article.organization_id)
                    .where(Article.status == "scored")
                    .order_by(Article.created_at.desc())
                    .limit(200)
                )
            ).all()

        if not rows:
            print("No articles stuck in 'scored'.")
            return

        print(f"Scoring {len(rows)} article(s) stuck in status=scored...")
        ok = 0
        fail = 0
        for article_id, org_id in rows:
            try:
                async with factory() as session:
                    wf = IntelligenceWorkflow(session, AIOrchestratorFactory.create())
                    result = await wf.run(org_id=org_id, article_id=article_id)
                    await session.commit()
                    ok += 1
                    print(
                        f"  {article_id} → score={result.get('score')} "
                        f"status={result.get('status')}"
                    )
            except Exception as exc:
                fail += 1
                print(f"  FAIL {article_id}: {exc}")

        print(f"Scoring done. ok={ok} fail={fail}")


if __name__ == "__main__":
    asyncio.run(main())
