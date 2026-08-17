"""Tests for the auto-relevance budget applied on newly-imported articles."""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.intelligence.application import autoscore_budget as budget_mod
from app.modules.news.application import post_ingest


class _FakeSettings:
    def __init__(self, cap: int, window_seconds: int = 3600) -> None:
        self.RELEVANCE_AUTOSCORE_MAX_PER_WINDOW = cap
        self.RELEVANCE_AUTOSCORE_WINDOW_SECONDS = window_seconds


@pytest.fixture(autouse=True)
def _bus(monkeypatch: pytest.MonkeyPatch) -> InProcessEventBus:
    bus = InProcessEventBus()
    monkeypatch.setattr(post_ingest, "get_event_bus", lambda: bus)
    return bus


@pytest.fixture(autouse=True)
def _fresh_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test gets its own budget instance so runs don't leak state."""
    fresh = budget_mod._RollingWindowBudget()
    monkeypatch.setattr(post_ingest, "autoscore_budget", fresh)
    monkeypatch.setattr(budget_mod, "get_settings", lambda: _FakeSettings(cap=100))


async def test_batch_larger_than_cap_only_publishes_cap_worth(
    monkeypatch: pytest.MonkeyPatch, _bus: InProcessEventBus
) -> None:
    seen: list[str] = []

    async def handler(event):
        seen.append(str(event.payload["article_id"]))

    _bus.subscribe("ArticleImported", handler)

    article_ids = [str(uuid.uuid4()) for _ in range(600)]
    await post_ingest.notify_articles_imported(
        org_id=uuid.uuid4(), source_id=uuid.uuid4(), article_ids=article_ids
    )

    assert len(seen) == 100
    assert seen == article_ids[:100]


async def test_batch_under_cap_publishes_all(
    monkeypatch: pytest.MonkeyPatch, _bus: InProcessEventBus
) -> None:
    seen: list[str] = []

    async def handler(event):
        seen.append(str(event.payload["article_id"]))

    _bus.subscribe("ArticleImported", handler)

    article_ids = [str(uuid.uuid4()) for _ in range(5)]
    await post_ingest.notify_articles_imported(
        org_id=uuid.uuid4(), source_id=uuid.uuid4(), article_ids=article_ids
    )

    assert len(seen) == 5


async def test_budget_shared_across_multiple_sources(
    monkeypatch: pytest.MonkeyPatch, _bus: InProcessEventBus
) -> None:
    """46 sources each importing 20 articles (the fresh-install scenario) —
    total scored across all calls must still respect the shared cap."""
    seen: list[str] = []

    async def handler(event):
        seen.append(str(event.payload["article_id"]))

    _bus.subscribe("ArticleImported", handler)

    for _ in range(46):
        article_ids = [str(uuid.uuid4()) for _ in range(20)]
        await post_ingest.notify_articles_imported(
            org_id=uuid.uuid4(), source_id=uuid.uuid4(), article_ids=article_ids
        )

    assert len(seen) == 100
