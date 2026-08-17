"""Unit tests for Publishing Plan window math, brand overrides, regenerate."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.content.application.calendar_awareness import FortnightCalendarAwareness
from app.modules.content.application.publishing_plan import (
    PublishingPlanService,
    PublishingPlanTargets,
    compute_gaps,
    days_left_in_fortnight,
    empty_counts,
    fortnight_window,
    is_plan_origin,
    load_publishing_plan_config,
    monday_of_week,
    normalize_mix_type,
    plan_window,
    resolve_targets_for_mode,
    weekly_window,
    workdays_in_fortnight,
    workdays_in_window,
)


def test_fortnight_window_current_plus_next_week() -> None:
    # Wednesday 5 Aug 2026 → Mon 3 Aug … Fri 14 Aug
    start, end = fortnight_window(date(2026, 8, 5))
    assert start == date(2026, 8, 3)
    assert end == date(2026, 8, 14)
    days = workdays_in_fortnight(start, end)
    assert len(days) == 10
    assert days[0] == date(2026, 8, 3)
    assert days[-1] == date(2026, 8, 14)
    assert all(d.weekday() < 5 for d in days)


def test_weekly_window_mon_fri() -> None:
    start, end = weekly_window(date(2026, 8, 5))
    assert start == date(2026, 8, 3)
    assert end == date(2026, 8, 7)
    days = workdays_in_window(start, end)
    assert len(days) == 5
    assert days[-1] == date(2026, 8, 7)


def test_plan_window_modes() -> None:
    assert plan_window("weekly", date(2026, 8, 5)) == weekly_window(date(2026, 8, 5))
    assert plan_window("fortnight", date(2026, 8, 5)) == fortnight_window(date(2026, 8, 5))


def test_fortnight_window_on_monday() -> None:
    start, end = fortnight_window(date(2026, 8, 3))
    assert start == date(2026, 8, 3)
    assert end == date(2026, 8, 14)


def test_fortnight_window_on_sunday_uses_that_week_monday() -> None:
    # Sunday 9 Aug 2026 is still in week starting Mon 3 Aug
    start, end = fortnight_window(date(2026, 8, 9))
    assert start == date(2026, 8, 3)
    assert end == date(2026, 8, 14)


def test_monday_of_week() -> None:
    assert monday_of_week(date(2026, 8, 5)) == date(2026, 8, 3)
    assert monday_of_week(date(2026, 8, 3)) == date(2026, 8, 3)


def test_compute_gaps() -> None:
    targets = {"educational": 6, "success_story": 3, "personal_achievement": 1}
    counts = {"educational": 2, "success_story": 1, "personal_achievement": 0}
    assert compute_gaps(targets, counts) == {
        "educational": 4,
        "success_story": 2,
        "personal_achievement": 1,
    }
    assert compute_gaps(targets, {"educational": 9, "success_story": 3, "personal_achievement": 2})[
        "educational"
    ] == 0


def test_days_left_counts_remaining_workdays() -> None:
    assert days_left_in_fortnight(date(2026, 8, 14), end=date(2026, 8, 14)) == 1
    assert days_left_in_fortnight(date(2026, 8, 3), end=date(2026, 8, 14)) == 10


def test_publishing_plan_config_defaults() -> None:
    load_publishing_plan_config.cache_clear()
    cfg = load_publishing_plan_config()
    assert cfg.default_window == "fortnight"
    assert cfg.targets.educational == 6
    assert cfg.targets.success_story == 3
    assert cfg.targets.personal_achievement == 1
    assert cfg.targets.total == 10
    assert cfg.windows["weekly"].educational == 3
    assert cfg.windows["weekly"].total == 5
    assert cfg.windows["fortnight"].total == 10
    assert "pending_review" in cfg.counting_statuses
    assert "rejected" not in cfg.counting_statuses
    assert "relevant" in cfg.educational_article_statuses


def test_resolve_targets_brand_override() -> None:
    load_publishing_plan_config.cache_clear()
    cfg = load_publishing_plan_config()
    overridden = resolve_targets_for_mode(
        cfg,
        "weekly",
        {"educational": 4, "success_story": 2, "personal_achievement": 0},
    )
    assert overridden == PublishingPlanTargets(4, 2, 0)
    base_weekly = resolve_targets_for_mode(cfg, "weekly", None)
    assert base_weekly.educational == 3


def test_is_plan_origin() -> None:
    assert is_plan_origin({"plan_origin": True}) is True
    assert is_plan_origin({"origin": "content_intelligence_plan"}) is True
    assert is_plan_origin({"origin": "manual_news"}) is False
    assert is_plan_origin({}) is False
    assert is_plan_origin(None) is False


def test_normalize_mix_type() -> None:
    assert normalize_mix_type("educational") == "educational"
    assert normalize_mix_type("success_story") == "success_story"
    assert normalize_mix_type("personal_achievement") == "personal_achievement"
    assert normalize_mix_type("thought_leadership") == "educational"
    assert normalize_mix_type("case_study") == "success_story"
    assert normalize_mix_type("unknown_thing") is None
    assert empty_counts() == {
        "educational": 0,
        "success_story": 0,
        "personal_achievement": 0,
    }


def test_fortnight_calendar_awareness_snapshot() -> None:
    cal = FortnightCalendarAwareness()
    ctx = cal.snapshot(uuid4())
    assert len(ctx.weekly_schedule) == 10
    assert ctx.frequency_ok is True


@pytest.mark.asyncio
async def test_fill_educational_skips_when_gap_zero() -> None:
    session = MagicMock()
    svc = PublishingPlanService(session)
    svc.get_plan = AsyncMock(
        return_value={
            "gaps": {"educational": 0, "success_story": 0, "personal_achievement": 0},
            "counts": {"educational": 6, "success_story": 3, "personal_achievement": 1},
            "window": {"mode": "fortnight"},
        }
    )
    generate = AsyncMock()
    svc._generate_uc = generate  # noqa: SLF001
    result = await svc.fill_educational(uuid4())
    assert result["generated"] == []
    assert result["gap_remaining"] == 0
    generate.execute.assert_not_called()


@pytest.mark.asyncio
async def test_regenerate_skips_when_all_gaps_zero() -> None:
    session = MagicMock()
    svc = PublishingPlanService(session)
    filled = {
        "gaps": {"educational": 0, "success_story": 0, "personal_achievement": 0},
        "counts": {"educational": 3, "success_story": 1, "personal_achievement": 1},
        "total_count": 5,
        "target": {"educational": 3, "success_story": 1, "personal_achievement": 1, "total": 5},
        "window": {"mode": "weekly", "start": "2026-08-03", "end": "2026-08-07"},
        "slots": [],
        "days_left": 3,
        "needs_capture": {},
        "review_queue": [],
    }
    svc.get_plan = AsyncMock(return_value=filled)
    svc.fill_educational = AsyncMock(
        return_value={"generated": [], "errors": [], "gap_remaining": 0, "message": "ok"}
    )
    svc.seed_calendar = AsyncMock(return_value={"assigned": 0, "skipped": 0, "assignments": []})
    generate = AsyncMock()
    svc._generate_uc = generate  # noqa: SLF001
    capture = AsyncMock()
    svc._capture_generate = capture  # noqa: SLF001

    result = await svc.regenerate_plan(uuid4())
    assert result["generated"] == []
    assert result["from_capture"] == []
    assert result["needs_capture"] == {}
    capture.execute.assert_not_called()
    svc.seed_calendar.assert_awaited_once()


@pytest.mark.asyncio
async def test_regenerate_fills_capture_and_queues_image() -> None:
    org_id = uuid4()
    session = MagicMock()
    svc = PublishingPlanService(session)

    plan_open = {
        "gaps": {"educational": 0, "success_story": 1, "personal_achievement": 0},
        "counts": {"educational": 6, "success_story": 2, "personal_achievement": 1},
        "total_count": 9,
        "target": {"educational": 6, "success_story": 3, "personal_achievement": 1, "total": 10},
        "window": {"mode": "fortnight", "start": "2026-08-03", "end": "2026-08-14"},
        "slots": [],
        "days_left": 8,
        "needs_capture": {"success_story": 1},
        "review_queue": [],
    }
    plan_closed = {
        **plan_open,
        "gaps": {"educational": 0, "success_story": 0, "personal_achievement": 0},
        "counts": {"educational": 6, "success_story": 3, "personal_achievement": 1},
        "total_count": 10,
        "needs_capture": {},
    }
    svc.get_plan = AsyncMock(side_effect=[plan_open, plan_open, plan_closed])
    svc.fill_educational = AsyncMock(
        return_value={"generated": [], "errors": [], "gap_remaining": 0, "message": "ok"}
    )
    svc.seed_calendar = AsyncMock(
        return_value={"assigned": 1, "skipped": 0, "assignments": [{"draft_id": "x"}]}
    )

    cap_sess = MagicMock()
    cap_sess.id = uuid4()
    cap_sess.title = "Win"
    cap_sess.content_type = "success_story"
    svc._ready_capture_sessions = AsyncMock(return_value=[cap_sess])  # noqa: SLF001

    draft_id = uuid4()
    capture = MagicMock()
    capture.execute = AsyncMock(
        return_value={
            "id": str(draft_id),
            "photo_count": 0,
            "content_type": "success_story",
        }
    )
    svc._capture_generate = capture  # noqa: SLF001

    svc._mark_plan_origin = AsyncMock()  # noqa: SLF001
    with patch.object(
        svc, "_ensure_draft_image", new=AsyncMock(return_value={"batch_job_id": "b1", "count": 1})
    ) as ensure_img:
        result = await svc.regenerate_plan(org_id)

    assert len(result["from_capture"]) == 1
    assert result["from_capture"][0]["draft_id"] == str(draft_id)
    ensure_img.assert_awaited_once()
    capture.execute.assert_awaited_once_with(org_id, cap_sess.id)
    svc._mark_plan_origin.assert_awaited()  # noqa: SLF001


@pytest.mark.asyncio
async def test_candidate_articles_skip_already_drafted() -> None:
    """Excluded when an article already has a plan-origin draft, or an approved
    draft of any origin (that one now counts toward the mix, so re-using it
    would double-post the same story). An undecided manual draft still must not
    block AI plan fill."""
    org_id = uuid4()
    used_article = uuid4()
    free_article = uuid4()
    manual_only = uuid4()
    approved_manual = uuid4()

    article = MagicMock()
    article.id = free_article
    article.title = "Free"
    article.summary = "s"
    article.status = "relevant"

    manual_article = MagicMock()
    manual_article.id = manual_only

    approved_manual_article = MagicMock()
    approved_manual_article.id = approved_manual

    used_result = MagicMock()
    used_result.all.return_value = [
        (used_article, {"plan_origin": True}, "pending_review"),
        (manual_only, {"origin": "manual_news"}, "pending_review"),
        (approved_manual, {"origin": "manual_news"}, "approved"),
    ]

    candidates_result = MagicMock()
    used_article_obj = MagicMock()
    used_article_obj.id = used_article
    candidates_result.all.return_value = [
        (used_article_obj, 90),
        (manual_article, 85),
        (approved_manual_article, 83),
        (article, 80),
    ]

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[used_result, candidates_result])

    svc = PublishingPlanService(session)
    out = await svc._candidate_educational_articles(org_id, limit=10)  # noqa: SLF001
    ids = {row[0].id for row in out}
    assert used_article not in ids
    assert approved_manual not in ids
    assert manual_only in ids
    assert free_article in ids
