"""MSRC (Microsoft Security Response Center) connector.

Fetches the latest security updates from the MSRC CVRF API
(api.msrc.microsoft.com/cvrf/v3.0/updates) and normalizes them.
Falls back to the MSRC RSS feed if the API is unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.core.logging import get_logger
from app.infrastructure.connectors.base import BaseConnector
from app.modules.news.domain.ports import NormalizedArticle

logger = get_logger(__name__)

_MSRC_UPDATES_URL = "https://api.msrc.microsoft.com/cvrf/v3.0/updates"
_MSRC_DETAIL_URL = "https://msrc.microsoft.com/update-guide/vulnerability"
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_ITEMS = 20


class MSRCConnector(BaseConnector):
    """Fetches security updates from the MSRC API."""

    connector_type = "msrc"

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        api_url: str = config.get("api_url", _MSRC_UPDATES_URL)
        max_items: int = config.get("max_items", _DEFAULT_MAX_ITEMS)

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    api_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "AIContentPlatform/1.0",
                    },
                    follow_redirects=True,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("MSRC API fetch failed: %s", exc)
            return await self._fallback_rss(config)

        try:
            data = response.json()
        except Exception:
            logger.error("MSRC API returned non-JSON response")
            return await self._fallback_rss(config)

        updates = data.get("value", [])
        if not isinstance(updates, list):
            logger.warning("MSRC API: unexpected 'value' type")
            return []

        # The endpoint also returns unrelated legacy release documents. Keep
        # the monthly security-update summaries used by the original GuardIQ
        # source and order them newest-first before applying the item limit.
        updates = [
            update
            for update in updates
            if "security updates" in str(update.get("DocumentTitle") or "").lower()
        ]
        updates.sort(
            key=lambda update: str(
                update.get("InitialReleaseDate")
                or update.get("CurrentReleaseDate")
                or ""
            ),
            reverse=True,
        )

        articles: list[NormalizedArticle] = []
        for update in updates[:max_items]:
            doc_id = update.get("ID", "")
            alias = update.get("Alias", doc_id)
            release_date = _parse_msrc_date(
                update.get("InitialReleaseDate") or update.get("CurrentReleaseDate", "")
            )
            url = f"{_MSRC_DETAIL_URL}/{doc_id}" if doc_id else ""
            title = f"MSRC {alias}: {update.get('DocumentTitle', 'Security Update')}"

            if not url:
                continue

            articles.append(
                NormalizedArticle(
                    title=title,
                    url=url,
                    summary=update.get("DocumentTitle", ""),
                    published_at=release_date,
                    author="Microsoft Security Response Center",
                    raw_payload=update,
                )
            )

        logger.info("MSRC connector fetched %d updates", len(articles))
        return articles

    async def _fallback_rss(self, config: dict) -> list[NormalizedArticle]:
        """Fall back to the MSRC RSS feed when the JSON API is unavailable."""
        from app.infrastructure.connectors.rss import RSSConnector

        rss = RSSConnector()
        fallback_url = config.get(
            "feed_url", "https://api.msrc.microsoft.com/update-guide/rss"
        )
        logger.info("MSRC falling back to RSS: %s", fallback_url)
        return await rss.fetch({"feed_url": fallback_url, **config})


def _parse_msrc_date(date_str: str) -> datetime | None:
    """Parse MSRC ISO-ish date strings."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
