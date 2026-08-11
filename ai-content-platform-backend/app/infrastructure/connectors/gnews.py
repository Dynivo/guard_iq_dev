"""GNews API connector — free-tier search endpoint.

Config:
  {
    "api_key": "...",           # or GNEWS_API_KEY env
    "api_endpoint": "https://gnews.io/api/v4/search",
    "query": "cybersecurity",
    "language": "en",
    "max_items": 25
  }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.connectors.base import BaseConnector
from app.modules.news.domain.ports import NormalizedArticle

logger = get_logger(__name__)

_DEFAULT_ENDPOINT = "https://gnews.io/api/v4/search"
_DEFAULT_TIMEOUT = 30.0


class GNewsConnector(BaseConnector):
    connector_type = "gnews"

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        key = (config.get("api_key") or "").strip() or (get_settings().GNEWS_API_KEY or "").strip()
        if not key:
            return False, "gnews: missing api_key / GNEWS_API_KEY"
        if not (config.get("query") or "").strip():
            return False, "gnews: missing query"
        return True, ""

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        api_key = (config.get("api_key") or "").strip() or (get_settings().GNEWS_API_KEY or "").strip()
        if not api_key:
            logger.error("GNews connector: missing api_key")
            return []
        query = (config.get("query") or "").strip()
        if not query:
            return []
        endpoint = (config.get("api_endpoint") or _DEFAULT_ENDPOINT).strip()
        max_items = max(1, min(int(config.get("max_items") or 25), 100))
        params: dict[str, Any] = {
            "apikey": api_key,
            "q": query,
            "max": min(max_items, 100),
            "lang": (config.get("language") or "en").strip() or "en",
        }
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("GNews fetch failed: %s", exc)
            return []

        articles: list[NormalizedArticle] = []
        for item in (data.get("articles") or [])[:max_items]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            published = _parse_iso(item.get("publishedAt"))
            articles.append(
                NormalizedArticle(
                    title=title,
                    url=url,
                    summary=str(item.get("description") or "")[:2000],
                    body_text=str(item.get("content") or item.get("description") or "")[:8000],
                    published_at=published,
                    author=(item.get("source") or {}).get("name")
                    if isinstance(item.get("source"), dict)
                    else None,
                    raw_payload=item,
                )
            )
        logger.info("GNews fetched %d articles", len(articles))
        return articles


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None
