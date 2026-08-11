"""Hacker News Firebase API connector (no API key).

Config:
  {
    "api_endpoint": "https://hacker-news.firebaseio.com/v0",
    "story_type": "topstories",   # topstories|newstories|beststories
    "max_items": 30,
    "min_score": 50
  }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.logging import get_logger
from app.infrastructure.connectors.base import BaseConnector
from app.modules.news.domain.ports import NormalizedArticle

logger = get_logger(__name__)

_DEFAULT_ENDPOINT = "https://hacker-news.firebaseio.com/v0"
_DEFAULT_TIMEOUT = 30.0
_ALLOWED_TYPES = frozenset({"topstories", "newstories", "beststories"})


class HackerNewsConnector(BaseConnector):
    connector_type = "hackernews"

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        story_type = (config.get("story_type") or "topstories").strip()
        if story_type not in _ALLOWED_TYPES:
            return False, f"hackernews: story_type must be one of {sorted(_ALLOWED_TYPES)}"
        return True, ""

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        base = (config.get("api_endpoint") or _DEFAULT_ENDPOINT).rstrip("/")
        story_type = (config.get("story_type") or "topstories").strip()
        if story_type not in _ALLOWED_TYPES:
            story_type = "topstories"
        max_items = max(1, min(int(config.get("max_items") or 30), 50))
        min_score = int(config.get("min_score") or 0)

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                ids_resp = await client.get(f"{base}/{story_type}.json")
                ids_resp.raise_for_status()
                ids = ids_resp.json() or []
                if not isinstance(ids, list):
                    return []
                articles: list[NormalizedArticle] = []
                for item_id in ids[: max_items * 2]:
                    if len(articles) >= max_items:
                        break
                    detail = await client.get(f"{base}/item/{item_id}.json")
                    if detail.status_code != 200:
                        continue
                    item = detail.json() or {}
                    if not isinstance(item, dict) or item.get("type") != "story":
                        continue
                    if int(item.get("score") or 0) < min_score:
                        continue
                    url = str(item.get("url") or "").strip()
                    if not url:
                        # Ask HN / text posts — use HN discussion URL
                        url = f"https://news.ycombinator.com/item?id={item_id}"
                    title = str(item.get("title") or "").strip()
                    if not title:
                        continue
                    published = None
                    if item.get("time"):
                        published = datetime.fromtimestamp(
                            int(item["time"]), tz=timezone.utc
                        )
                    articles.append(
                        NormalizedArticle(
                            title=title,
                            url=url,
                            summary=str(item.get("text") or "")[:2000],
                            body_text=str(item.get("text") or "")[:8000],
                            published_at=published,
                            author=str(item.get("by") or "") or None,
                            raw_payload=item,
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.error("Hacker News fetch failed: %s", exc)
            return []

        logger.info("Hacker News fetched %d articles", len(articles))
        return articles
