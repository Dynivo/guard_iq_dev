"""Tests for the cron due-ness check used by the source refresh loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.news.application.source_cron import _is_due


def test_never_fetched_is_due_immediately() -> None:
    assert _is_due("0 */3 * * *", None, datetime.now(timezone.utc)) is True


def test_not_due_before_next_cron_fire() -> None:
    last = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    now = last + timedelta(hours=1)  # next fire for */3h is 03:00
    assert _is_due("0 */3 * * *", last, now) is False


def test_due_after_next_cron_fire() -> None:
    last = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    now = last + timedelta(hours=3, minutes=1)
    assert _is_due("0 */3 * * *", last, now) is True


def test_malformed_cron_is_not_due() -> None:
    last = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    now = last + timedelta(days=30)
    assert _is_due("not a cron", last, now) is False
