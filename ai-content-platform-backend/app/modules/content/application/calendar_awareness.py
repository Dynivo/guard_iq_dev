"""Calendar Awareness — fortnight Publishing Plan window for planner context."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.modules.content.application.publishing_plan import (
    fortnight_window,
    workdays_in_fortnight,
)
from app.modules.content.domain.models import CalendarContext


class FortnightCalendarAwareness:
    """Exposes the current bi-weekly Mon–Fri workday schedule to the planner."""

    def snapshot(
        self, org_id: uuid.UUID, now: datetime | None = None
    ) -> CalendarContext:
        _ = org_id
        today = (now or datetime.now(timezone.utc)).date()
        start, end = fortnight_window(today)
        days = workdays_in_fortnight(start, end)
        return CalendarContext(
            today_generated_count=0,
            weekly_schedule=tuple(d.isoformat() for d in days),
            frequency_ok=True,
            upcoming_events=(),
        )


# Backward-compatible name — planner historically imported StubCalendarAwareness.
StubCalendarAwareness = FortnightCalendarAwareness
