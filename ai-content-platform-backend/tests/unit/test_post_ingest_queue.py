"""Tests for command-driven relevance screening after ingest."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.modules.intelligence.application.subscribers import (
    register_intelligence_handlers,
)
from app.modules.news.application.post_ingest import notify_articles_imported


async def test_post_ingest_never_starts_llm_screening(monkeypatch) -> None:
    messages: list[tuple] = []
    monkeypatch.setattr(
        "app.modules.news.application.post_ingest.logger.info",
        lambda *args: messages.append(args),
    )

    article_ids = [str(uuid.uuid4()) for _ in range(600)]
    await notify_articles_imported(
        org_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        article_ids=article_ids,
    )

    assert messages
    assert messages[0][1] == 600


def test_article_import_event_does_not_start_automatic_screening() -> None:
    bus = MagicMock()

    register_intelligence_handlers(bus, session_factory=MagicMock())

    bus.subscribe.assert_not_called()
