"""Unit tests for enterprise free news catalog + new connectors."""

from __future__ import annotations

import pytest

from app.infrastructure.connectors.registry import get_connector, list_connector_types
from app.modules.news.application.source_catalog import load_enterprise_source_catalog


def test_enterprise_catalog_loads_expected_categories() -> None:
    load_enterprise_source_catalog.cache_clear()
    items = load_enterprise_source_catalog()
    assert len(items) >= 40
    categories = {i["category"] for i in items}
    assert "government" in categories
    assert "vendor" in categories
    assert "threat_intelligence" in categories
    assert "ai" in categories
    assert "cloud" in categories
    # No empty feed for RSS entries
    for item in items:
        if item["connector_type"] == "rss":
            assert item["config"].get("feed_url")
        assert 0 <= item["credibility_score"] <= 100
        assert item["schedule_cron"]


def test_new_connectors_registered() -> None:
    types = set(list_connector_types())
    for name in ("rss", "news_api", "gnews", "guardian", "currents", "hackernews"):
        assert name in types
        connector = get_connector(name)
        assert connector.connector_type == name


@pytest.mark.asyncio
async def test_hackernews_validate_config() -> None:
    connector = get_connector("hackernews")
    ok, err = await connector.validate_config({"story_type": "topstories"})
    assert ok and err == ""
    bad, msg = await connector.validate_config({"story_type": "nope"})
    assert not bad and "story_type" in msg


@pytest.mark.asyncio
async def test_gnews_requires_key_and_query() -> None:
    connector = get_connector("gnews")
    ok, _ = await connector.validate_config({"query": "ai"})
    # May pass if GNEWS_API_KEY set in env; otherwise fail
    if not ok:
        ok2, msg = await connector.validate_config({"api_key": "x", "query": ""})
        assert not ok2
        assert "query" in msg
