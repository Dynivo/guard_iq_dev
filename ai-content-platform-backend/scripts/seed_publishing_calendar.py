#!/usr/bin/env python3
"""Seed publishing calendar labels for an org (assign drafts onto plan workdays).

Usage:
  .venv/bin/python scripts/seed_publishing_calendar.py [--org-id UUID] [--rebalance]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.infrastructure.postgres.models.identity import Organization
from app.infrastructure.postgres.session import async_session_factory
from app.modules.content.application.calendar_view import CalendarViewService
from app.modules.content.application.publishing_plan import PublishingPlanService

DEFAULT_ORG = "6092c681-54ea-47a7-86b3-9e9f42891590"  # Guard IQ


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed publishing calendar for an org")
    parser.add_argument("--org-id", default=DEFAULT_ORG)
    parser.add_argument("--rebalance", action="store_true")
    args = parser.parse_args()
    org_id = uuid.UUID(args.org_id)

    async with async_session_factory() as session:
        org = (
            await session.execute(select(Organization).where(Organization.id == org_id))
        ).scalar_one_or_none()
        if org is None:
            # Fall back to name match
            org = (
                await session.execute(
                    select(Organization).where(Organization.name.ilike("%guard%")).limit(1)
                )
            ).scalar_one_or_none()
            if org is None:
                print("Organization not found", file=sys.stderr)
                return 1
            org_id = org.id

        svc = PublishingPlanService(session)
        result = await svc.seed_calendar(org_id, rebalance=args.rebalance)
        await session.commit()

        cal = await CalendarViewService(session).month_view(org_id)
        print(f"org={org.name} ({org_id})")
        print(f"window={result.get('window')}")
        print(
            f"assigned={result.get('assigned')} skipped={result.get('skipped')} "
            f"cleared_manual={result.get('cleared_manual')}"
        )
        print(f"load={result.get('load')}")
        print(f"calendar_month={cal.get('month_label')} events={len(cal.get('events') or [])}")
        for ev in (cal.get("events") or [])[:20]:
            print(f"  {ev.get('date')}  {ev.get('title')}")
        if len(cal.get("events") or []) > 20:
            print(f"  … +{len(cal['events']) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
