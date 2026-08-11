"""RSS feed connector using feedparser + httpx async fetch.

Works for any standard RSS/Atom feed. Config expects:
  {"feed_url": "https://example.com/feed.xml"}
Optional:
  {"max_items": 50}  — default 50
"""

from __future__ import annotations

from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

from app.core.logging import get_logger
from app.infrastructure.connectors.base import BaseConnector
from app.modules.news.domain.ports import NormalizedArticle

logger = get_logger(__name__)

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_ITEMS = 50


class RSSConnector(BaseConnector):
    """Fetches and normalizes RSS/Atom feeds."""

    connector_type = "rss"

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        if not (config.get("feed_url") or "").strip():
            return False, "rss: missing feed_url"
        return True, ""

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        feed_url: str = config.get("feed_url", "")
        if not feed_url:
            logger.error("RSS connector: missing feed_url in config")
            return []

        max_items: int = config.get("max_items", _DEFAULT_MAX_ITEMS)

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    feed_url,
                    headers={"User-Agent": "AIContentPlatform/1.0"},
                    follow_redirects=True,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("RSS fetch failed for %s: %s", feed_url, exc)
            return []

        parsed = feedparser.parse(response.text)
        if parsed.bozo and not parsed.entries:
            logger.warning("RSS parse returned no entries for %s", feed_url)
            return []

        articles: list[NormalizedArticle] = []
        for entry in parsed.entries[:max_items]:
            published_at = _parse_entry_date(entry)
            article = NormalizedArticle(
                title=_clean_text(entry.get("title", "")),
                url=entry.get("link", ""),
                summary=_clean_text(entry.get("summary", "")),
                body_text=_extract_body(entry),
                published_at=published_at,
                author=entry.get("author"),
                raw_payload=dict(entry),
            )
            if article.url:
                articles.append(article)

        logger.info("RSS connector fetched %d articles from %s", len(articles), feed_url)
        return articles


def _parse_entry_date(entry: dict) -> datetime | None:
    """Try to extract a timezone-aware datetime from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        time_struct = entry.get(field)
        if time_struct:
            try:
                return datetime.fromtimestamp(mktime(time_struct), tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue
    return None


def _clean_text(text: str | None) -> str:
    """Strip HTML tags from feed text via a simple approach."""
    if not text:
        return ""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    return " ".join(clean.split()).strip()


def _extract_body(entry: dict) -> str | None:
    """Extract full body content if available in content:encoded or content."""
    content_list = entry.get("content", [])
    if content_list and isinstance(content_list, list):
        for item in content_list:
            value = item.get("value", "")
            if value:
                return _clean_text(value)
    return None
