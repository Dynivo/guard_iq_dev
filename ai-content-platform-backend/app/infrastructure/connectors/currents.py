"""Currents API connector.

Config:
  {
    "api_key": "...",  # or CURRENTS_API_KEY
    "api_endpoint": "https://api.currentsapi.services/v1/latest-news",
    "language": "en",
    "category": "technology",
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

_DEFAULT_ENDPOINT = "https://api.currentsapi.services/v1/latest-news"
_DEFAULT_TIMEOUT = 30.0


class CurrentsConnector(BaseConnector):
    connector_type = "currents"

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        key = (config.get("api_key") or "").strip() or (get_settings().CURRENTS_API_KEY or "").strip()
        if not key:
            return False, "currents: missing api_key / CURRENTS_API_KEY"
        return True, ""

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        api_key = (config.get("api_key") or "").strip() or (
            get_settings().CURRENTS_API_KEY or ""
        ).strip()
        if not api_key:
            logger.error("Currents connector: missing api_key")
            return []
        endpoint = (config.get("api_endpoint") or _DEFAULT_ENDPOINT).strip()
        max_items = max(1, min(int(config.get("max_items") or 25), 100))
        params: dict[str, Any] = {
            "apiKey": api_key,
            "language": (config.get("language") or "en").strip() or "en",
        }
        category = (config.get("category") or "").strip()
        if category:
            params["category"] = category
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("Currents fetch failed: %s", exc)
            return []

        articles: list[NormalizedArticle] = []
        for item in (data.get("news") or [])[:max_items]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            articles.append(
                NormalizedArticle(
                    title=title,
                    url=url,
                    summary=str(item.get("description") or "")[:2000],
                    body_text=str(item.get("description") or "")[:8000],
                    published_at=_parse_iso(item.get("published")),
                    author=str(item.get("author") or "") or None,
                    raw_payload=item,
                )
            )
        logger.info("Currents fetched %d articles", len(articles))
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
