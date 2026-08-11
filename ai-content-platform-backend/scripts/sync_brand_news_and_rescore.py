#!/usr/bin/env python3
"""Sync Brand Memory → news queries + relevance profile, then soft-rescore articles.

Usage:
    cd ai-content-platform-backend
    .venv/bin/python scripts/sync_brand_news_and_rescore.py
    .venv/bin/python scripts/sync_brand_news_and_rescore.py --org-id <uuid> --limit 80
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.constants import ArticleStatus
from app.infrastructure.postgres.models.identity import Organization
from app.infrastructure.postgres.models.news import Article
from app.infrastructure.postgres.session import async_session_factory
from app.modules.brand_intelligence.application.news_policy_service import (
    BrandNewsPolicyService,
)
from app.modules.intelligence.application.workflow import IntelligenceWorkflow


async def _resolve_org(session, org_id: uuid.UUID | None) -> uuid.UUID:
    if org_id:
        return org_id
    row = (
        await session.execute(select(Organization).order_by(Organization.created_at.asc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        raise RuntimeError("No organization found")
    print(f"  Org: {row.name} ({row.id})")
    return row.id


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", type=uuid.UUID, default=None)
    parser.add_argument("--profile-id", type=uuid.UUID, default=None)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--skip-rescore", action="store_true")
    args = parser.parse_args()

    print("=== Sync brand news policy + rescore ===")
    async with async_session_factory() as session:
        org_id = await _resolve_org(session, args.org_id)
        svc = BrandNewsPolicyService(session)
        result = await svc.sync_news_sources(org_id, profile_id=args.profile_id)
        await session.commit()
        policy = result.get("policy") or {}
        print(f"  Primary query: {policy.get('primary_query')}")
        print(f"  Topics: {policy.get('topics')}")
        print(f"  Sources updated: {result.get('sources_updated')}")
        print(f"  Relevance profile projected from: {policy.get('source')}")

        if args.skip_rescore:
            print("  Skipped rescore")
            return

        # Prefer recent scored/raw/irrelevant articles for brand re-ranking
        statuses = (
            ArticleStatus.SCORED,
            ArticleStatus.RAW,
            ArticleStatus.RELEVANT,
            ArticleStatus.IRRELEVANT,
            "scored",
            "raw",
            "relevant",
            "irrelevant",
        )
        rows = (
            await session.execute(
                select(Article.id)
                .where(
                    Article.organization_id == org_id,
                    Article.status.in_(statuses),
                )
                .order_by(Article.created_at.desc())
                .limit(args.limit)
            )
        ).scalars().all()
        print(f"  Rescoring {len(rows)} articles…")
        wf = IntelligenceWorkflow(session)
        ok_n = fail_n = 0
        for aid in rows:
            try:
                await wf.run(org_id, aid)
                ok_n += 1
            except Exception as exc:  # noqa: BLE001
                fail_n += 1
                print(f"    fail {aid}: {exc}")
        await session.commit()
        print(f"=== Done: rescored_ok={ok_n} fail={fail_n} ===")


if __name__ == "__main__":
    asyncio.run(main())
