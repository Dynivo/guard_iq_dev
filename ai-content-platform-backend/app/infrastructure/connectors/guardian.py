"""Guardian Open Platform connector.

Config:
  {
    "api_key": "...",  # or GUARDIAN_API_KEY
    "api_endpoint": "https://content.guardianapis.com/search",
    "query": "...",
    "section": "technology",
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

_DEFAULT_ENDPOINT = "https://content.guardianapis.com/search"
_DEFAULT_TIMEOUT = 30.0


class GuardianConnector(BaseConnector):
    connector_type = "guardian"

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        key = (config.get("api_key") or "").strip() or (get_settings().GUARDIAN_API_KEY or "").strip()
        if not key:
            return False, "guardian: missing api_key / GUARDIAN_API_KEY"
        return True, ""

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        api_key = (config.get("api_key") or "").strip() or (
            get_settings().GUARDIAN_API_KEY or ""
        ).strip()
        if not api_key:
            logger.error("Guardian connector: missing api_key")
            return []
        endpoint = (config.get("api_endpoint") or _DEFAULT_ENDPOINT).strip()
        max_items = max(1, min(int(config.get("max_items") or 25), 50))
        params: dict[str, Any] = {
            "api-key": api_key,
            "page-size": max_items,
            "show-fields": "trailText,bodyText,byline",
            "order-by": "newest",
        }
        query = (config.get("query") or "").strip()
        if query:
            params["q"] = query
        section = (config.get("section") or "").strip()
        if section:
            params["section"] = section
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("Guardian fetch failed: %s", exc)
            return []

        results = ((data.get("response") or {}).get("results") or [])
        articles: list[NormalizedArticle] = []
        for item in results[:max_items]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("webUrl") or "").strip()
            title = str(item.get("webTitle") or "").strip()
            if not url or not title:
                continue
            fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
            articles.append(
                NormalizedArticle(
                    title=title,
                    url=url,
                    summary=str(fields.get("trailText") or "")[:2000],
                    body_text=str(fields.get("bodyText") or fields.get("trailText") or "")[:8000],
                    published_at=_parse_iso(item.get("webPublicationDate")),
                    author=str(fields.get("byline") or "") or None,
                    raw_payload=item,
                )
            )
        logger.info("Guardian fetched %d articles", len(articles))
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
