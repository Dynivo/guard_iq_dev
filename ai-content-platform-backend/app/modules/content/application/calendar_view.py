"""Monthly publishing calendar — scheduled posts + plan slot suggestions."""

from __future__ import annotations

import calendar as cal_mod
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DraftStatus
from app.infrastructure.postgres.models.content import Draft
from app.modules.content.application.publishing_plan import (
    PublishingPlanService,
    is_plan_origin,
    normalize_mix_type,
)


_CALENDAR_STATUSES = (
    DraftStatus.PENDING_REVIEW,
    DraftStatus.IN_REVIEW,
    DraftStatus.APPROVED,
    DraftStatus.PUBLISHED,
    "pending_review",
    "in_review",
    "approved",
    "published",
    "scheduled",
)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = cal_mod.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def grid_bounds(year: int, month: int) -> tuple[date, date]:
    """Monday-start grid covering the full month (Google-style weeks)."""
    start, end = month_bounds(year, month)
    # Monday = 0
    grid_start = start - timedelta(days=start.weekday())
    # Pad to complete final week (Sunday)
    days_after = 6 - end.weekday()
    grid_end = end + timedelta(days=days_after)
    return grid_start, grid_end


class CalendarViewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._plan = PublishingPlanService(session)

    async def month_view(
        self,
        org_id: uuid.UUID,
        *,
        year: int | None = None,
        month: int | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        today = today or date.today()
        year = year or today.year
        month = month or today.month
        if month < 1 or month > 12:
            raise ValueError("month must be 1–12")
        if year < 2000 or year > 2100:
            raise ValueError("year out of range")

        month_start, month_end = month_bounds(year, month)
        grid_start, grid_end = grid_bounds(year, month)
        plan = await self._plan.get_plan(org_id, today=today)

        drafts = await self._fetch_calendar_drafts(org_id)
        events: list[dict[str, Any]] = []
        unscheduled: list[dict[str, Any]] = []
        scheduled_dates: set[str] = set()

        mix_short = {
            "educational": "Edu",
            "success_story": "Success",
            "personal_achievement": "Personal",
        }

        for d in drafts:
            meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
            # Manual News drafts only surface here once a decision has been made
            # (approved/published) — undecided ones stay in the Drafts review queue.
            decided = d.status in (
                DraftStatus.APPROVED,
                DraftStatus.PUBLISHED,
                "approved",
                "published",
            )
            if not is_plan_origin(meta) and not decided:
                continue
            scheduled = meta.get("scheduled_for")
            mix = normalize_mix_type(d.content_type) or (
                str(meta.get("calendar_label") or "") or None
            )
            hook = (d.hook or "").strip() or "Untitled post"
            prefix = mix_short.get(mix or "", "")
            title = f"{prefix}: {hook}" if prefix else hook
            item = {
                "id": str(d.id),
                "draft_id": str(d.id),
                "kind": "post",
                "title": title[:80],
                "content_type": d.content_type,
                "mix_type": mix,
                "status": d.status,
                "date": scheduled if isinstance(scheduled, str) else None,
                "suggested": False,
                "label": mix,
            }
            is_placeable = d.status in (
                DraftStatus.APPROVED,
                DraftStatus.PUBLISHED,
                "approved",
                "published",
            )
            if isinstance(scheduled, str) and len(scheduled) >= 10:
                if not is_placeable:
                    # Stale/legacy scheduling on a not-yet-approved draft — never render it.
                    continue
                day = scheduled[:10]
                item["date"] = day
                scheduled_dates.add(day)
                try:
                    date.fromisoformat(day)
                except ValueError:
                    unscheduled.append(item)
                    continue
                events.append(item)
            else:
                # Only approved posts are ready to schedule — pending-review drafts
                # still need a decision in the review queue first.
                if d.status in (DraftStatus.APPROVED, "approved"):
                    unscheduled.append(item)

        # Plan open slots → suggested events (no draft yet)
        for slot in plan.get("slots") or []:
            day = slot.get("date")
            if not day or day in scheduled_dates:
                continue
            if not slot.get("open"):
                # Assigned slot without scheduled_for still listed via draft items above
                for it in slot.get("items") or []:
                    did = it.get("draft_id")
                    if did and not any(e.get("draft_id") == did for e in events):
                        events.append(
                            {
                                "id": f"slot-{day}-{did}",
                                "draft_id": did,
                                "kind": "post",
                                "title": "Planned post",
                                "content_type": it.get("content_type"),
                                "mix_type": normalize_mix_type(it.get("content_type")),
                                "status": it.get("status") or "planned",
                                "date": day,
                                "suggested": True,
                            }
                        )
                continue
            suggested_ct = slot.get("suggested_content_type")
            if not suggested_ct:
                continue
            try:
                sd = date.fromisoformat(str(day)[:10])
            except ValueError:
                continue
            if not (grid_start <= sd <= grid_end):
                continue
            label = str(suggested_ct).replace("_", " ").title()
            events.append(
                {
                    "id": f"plan-{day}-{suggested_ct}",
                    "draft_id": None,
                    "kind": "plan_slot",
                    "title": f"Plan · {label}",
                    "content_type": suggested_ct,
                    "mix_type": suggested_ct,
                    "status": "planned",
                    "date": str(day)[:10],
                    "suggested": True,
                }
            )

        # Sort events by date then title
        events.sort(key=lambda e: (e.get("date") or "", e.get("title") or ""))

        weeks: list[list[dict[str, Any]]] = []
        cur = grid_start
        while cur <= grid_end:
            week: list[dict[str, Any]] = []
            for _ in range(7):
                key = cur.isoformat()
                day_events = [e for e in events if e.get("date") == key]
                week.append(
                    {
                        "date": key,
                        "day": cur.day,
                        "in_month": cur.month == month,
                        "is_today": cur == today,
                        "is_weekend": cur.weekday() >= 5,
                        "events": day_events,
                    }
                )
                cur += timedelta(days=1)
            weeks.append(week)

        return {
            "year": year,
            "month": month,
            "month_label": date(year, month, 1).strftime("%B %Y"),
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
            "grid_start": grid_start.isoformat(),
            "grid_end": grid_end.isoformat(),
            "weeks": weeks,
            "events": [e for e in events if e.get("date") and month_start.isoformat() <= e["date"] <= month_end.isoformat()],
            "unscheduled": unscheduled[:40],
            "plan_window": plan.get("window"),
            "plan_gaps": plan.get("gaps"),
            "quota_hint": (
                f"{(plan.get('target') or {}).get('total', 10)} posts / "
                f"{(plan.get('window') or {}).get('mode', 'fortnight')}"
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_calendar_drafts(self, org_id: uuid.UUID) -> list[Draft]:
        stmt = (
            select(Draft)
            .where(
                Draft.organization_id == org_id,
                Draft.status.in_(_CALENDAR_STATUSES),
            )
            .order_by(Draft.updated_at.desc())
            .limit(300)
        )
        return list((await self._session.execute(stmt)).scalars().all())
