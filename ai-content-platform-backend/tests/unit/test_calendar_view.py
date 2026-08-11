"""Unit tests for monthly calendar grid math."""

from __future__ import annotations

from datetime import date

from app.modules.content.application.calendar_view import grid_bounds, month_bounds


def test_month_bounds_august_2026() -> None:
    start, end = month_bounds(2026, 8)
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


def test_grid_bounds_starts_monday_pads_sunday() -> None:
    # Aug 2026: Sat 1 … Mon 31 → grid Mon Jul 27 … Sun Sep 6
    start, end = grid_bounds(2026, 8)
    assert start == date(2026, 7, 27)
    assert start.weekday() == 0
    assert end == date(2026, 9, 6)
    assert end.weekday() == 6
    days = (end - start).days + 1
    assert days % 7 == 0
    assert days >= 31
