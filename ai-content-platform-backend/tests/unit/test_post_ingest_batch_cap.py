"""Tests for the auto-relevance batch cap applied on newly-imported articles."""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.events.in_process_bus import InProcessEventBus
from app.modules.news.application import post_ingest


@pytest.fixture(autouse=True)
def _bus(monkeypatch: pytest.MonkeyPatch) -> InProcessEventBus:
    bus = InProcessEventBus()
    monkeypatch.setattr(post_ingest, "get_event_bus", lambda: bus)
    return bus


def _set_cap(monkeypatch: pytest.MonkeyPatch, cap: int) -> None:
    settings = post_ingest.get_settings()
    monkeypatch.setattr(
        post_ingest, "get_settings", lambda: settings.model_copy(update={"RELEVANCE_AUTOSCORE_BATCH_CAP": cap})
    )


async def test_batch_larger_than_cap_only_publishes_cap_worth(
    monkeypatch: pytest.MonkeyPatch, _bus: InProcessEventBus
) -> None:
    _set_cap(monkeypatch, 100)
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
    _set_cap(monkeypatch, 100)
    seen: list[str] = []

    async def handler(event):
        seen.append(str(event.payload["article_id"]))

    _bus.subscribe("ArticleImported", handler)

    article_ids = [str(uuid.uuid4()) for _ in range(5)]
    await post_ingest.notify_articles_imported(
        org_id=uuid.uuid4(), source_id=uuid.uuid4(), article_ids=article_ids
    )

    assert len(seen) == 5
