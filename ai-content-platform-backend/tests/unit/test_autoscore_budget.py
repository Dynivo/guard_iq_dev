"""Tests for the process-wide rolling-window auto-relevance-scoring budget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.intelligence.application.autoscore_budget import _RollingWindowBudget


class _FakeSettings:
    def __init__(self, cap: int, window_seconds: int) -> None:
        self.RELEVANCE_AUTOSCORE_MAX_PER_WINDOW = cap
        self.RELEVANCE_AUTOSCORE_WINDOW_SECONDS = window_seconds


def _patch_settings(monkeypatch: pytest.MonkeyPatch, cap: int, window_seconds: int = 3600) -> None:
    import app.modules.intelligence.application.autoscore_budget as mod

    monkeypatch.setattr(mod, "get_settings", lambda: _FakeSettings(cap, window_seconds))


def test_single_reserve_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, cap=100)
    budget = _RollingWindowBudget()
    assert budget.reserve(600) == 100


def test_budget_shared_across_many_small_reserves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates 46 sources each ingesting ~20 articles — the exact scenario
    where a per-batch cap would let everything through but a shared budget
    should not."""
    _patch_settings(monkeypatch, cap=100)
    budget = _RollingWindowBudget()
    granted_total = 0
    for _ in range(46):
        granted_total += budget.reserve(20)
    assert granted_total == 100


def test_window_resets_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, cap=100, window_seconds=60)
    budget = _RollingWindowBudget()
    assert budget.reserve(100) == 100
    assert budget.reserve(10) == 0  # exhausted within the same window

    # Simulate the window having expired.
    budget._window_start = datetime.now(timezone.utc) - timedelta(seconds=61)
    assert budget.reserve(10) == 10


def test_zero_or_negative_cap_means_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, cap=0)
    budget = _RollingWindowBudget()
    assert budget.reserve(600) == 600
