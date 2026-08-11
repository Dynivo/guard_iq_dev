"""Unit tests for the RSS connector with mocked httpx responses."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.connectors.rss import RSSConnector

_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article One</title>
      <link>https://example.com/article-1</link>
      <description>Summary of article one</description>
      <pubDate>Mon, 01 Jul 2024 12:00:00 GMT</pubDate>
      <author>Author A</author>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/article-2</link>
      <description>&lt;p&gt;HTML summary&lt;/p&gt;</description>
      <pubDate>Tue, 02 Jul 2024 14:30:00 GMT</pubDate>
    </item>
    <item>
      <title></title>
      <link>https://example.com/no-title</link>
      <description>No title article</description>
    </item>
  </channel>
</rss>"""


class _MockResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("GET", "http://x"), response=self  # type: ignore
            )


@pytest.mark.asyncio
async def test_rss_connector_parses_items() -> None:
    connector = RSSConnector()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_MockResponse(_SAMPLE_RSS))

    with patch("app.infrastructure.connectors.rss.httpx.AsyncClient", return_value=mock_client):
        articles = await connector.fetch({"feed_url": "https://example.com/feed"})

    assert len(articles) == 3
    assert articles[0].title == "Article One"
    assert articles[0].url == "https://example.com/article-1"
    assert articles[0].summary == "Summary of article one"
    assert articles[0].author == "Author A"
    assert articles[0].published_at is not None


@pytest.mark.asyncio
async def test_rss_connector_strips_html_from_summary() -> None:
    connector = RSSConnector()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_MockResponse(_SAMPLE_RSS))

    with patch("app.infrastructure.connectors.rss.httpx.AsyncClient", return_value=mock_client):
        articles = await connector.fetch({"feed_url": "https://example.com/feed"})

    assert "<p>" not in (articles[1].summary or "")
    assert "HTML summary" in (articles[1].summary or "")


@pytest.mark.asyncio
async def test_rss_connector_returns_empty_on_missing_url() -> None:
    connector = RSSConnector()
    articles = await connector.fetch({})
    assert articles == []


@pytest.mark.asyncio
async def test_rss_connector_returns_empty_on_http_error() -> None:
    connector = RSSConnector()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_MockResponse("", status_code=500))

    with patch("app.infrastructure.connectors.rss.httpx.AsyncClient", return_value=mock_client):
        articles = await connector.fetch({"feed_url": "https://example.com/feed"})

    assert articles == []


@pytest.mark.asyncio
async def test_rss_connector_respects_max_items() -> None:
    connector = RSSConnector()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_MockResponse(_SAMPLE_RSS))

    with patch("app.infrastructure.connectors.rss.httpx.AsyncClient", return_value=mock_client):
        articles = await connector.fetch({"feed_url": "https://example.com/feed", "max_items": 1})

    assert len(articles) == 1
    assert articles[0].title == "Article One"


@pytest.mark.asyncio
async def test_rss_connector_raw_payload_present() -> None:
    connector = RSSConnector()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_MockResponse(_SAMPLE_RSS))

    with patch("app.infrastructure.connectors.rss.httpx.AsyncClient", return_value=mock_client):
        articles = await connector.fetch({"feed_url": "https://example.com/feed"})

    assert articles[0].raw_payload is not None
    assert "title" in articles[0].raw_payload
