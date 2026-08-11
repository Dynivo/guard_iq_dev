"""NewsData.io API connector.

Fetches articles from the NewsData.io latest news endpoint.

Config (all optional except api key via env fallback):
  {
    "api_key": "...",
    "query": "",                    # optional keyword search
    "language": "en",
    "country": "gb",
    "categories": ["technology", "business"],  # multi-select, max 5
    "category": "technology",       # legacy single value still supported
    "max_items": 50,                # may paginate; free plan ≈10/page
    "paid_plan": false              # when true, size may go up to 50/page
  }

Empty query + empty categories is valid: returns latest news.
Free plans fail if size > 10 — we cap automatically unless paid_plan=true.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.connectors.base import BaseConnector
from app.modules.news.application.category_utils import normalize_category
from app.modules.news.domain.ports import NormalizedArticle

logger = get_logger(__name__)

_NEWSDATA_BASE = "https://newsdata.io/api/1/latest"
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_ITEMS = 50
_FREE_PAGE_SIZE = 10
_PAID_PAGE_SIZE = 50

# Official NewsData category values (up to 5 per request).
NEWSDATA_CATEGORIES: tuple[str, ...] = (
    "business",
    "crime",
    "domestic",
    "education",
    "entertainment",
    "environment",
    "food",
    "health",
    "lifestyle",
    "politics",
    "science",
    "sports",
    "technology",
    "top",
    "tourism",
    "world",
    "other",
)


def _env_newsdata_key() -> str:
    return (get_settings().NEWSDATA_API_KEY or "").strip()


def _categories_from_config(config: dict[str, Any]) -> list[str]:
    raw = config.get("categories")
    if isinstance(raw, list):
        values = [str(v).strip().lower() for v in raw if str(v).strip()]
    elif isinstance(raw, str) and raw.strip():
        values = [p.strip().lower() for p in raw.split(",") if p.strip()]
    else:
        legacy = (config.get("category") or "").strip().lower()
        values = [legacy] if legacy else []
    allowed = set(NEWSDATA_CATEGORIES)
    # Preserve order, unique, max 5 (API limit)
    out: list[str] = []
    for value in values:
        if value in allowed and value not in out:
            out.append(value)
        if len(out) >= 5:
            break
    return out


class NewsDataConnector(BaseConnector):
    """Fetches from the NewsData.io REST API."""

    connector_type = "news_api"

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        api_key = (config.get("api_key") or "").strip() or _env_newsdata_key()
        if not api_key:
            return False, "news_api: missing api_key"
        return True, ""

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        api_key: str = (config.get("api_key") or "").strip() or _env_newsdata_key()
        if not api_key:
            logger.error("NewsData connector: missing api_key in config")
            return []

        max_items = int(config.get("max_items") or _DEFAULT_MAX_ITEMS)
        max_items = max(1, min(max_items, 100))
        paid = bool(config.get("paid_plan"))
        page_size = min(max_items, _PAID_PAGE_SIZE if paid else _FREE_PAGE_SIZE)

        params: dict[str, Any] = {
            "apikey": api_key,
            "size": page_size,
        }
        query = (config.get("query") or "").strip()
        if query:
            params["q"] = query
        language = (config.get("language") or "").strip()
        if language:
            params["language"] = language
        country = (config.get("country") or "").strip()
        if country:
            params["country"] = country
        categories = _categories_from_config(config)
        if categories:
            params["category"] = ",".join(categories)

        articles: list[NormalizedArticle] = []
        next_page: str | None = None
        pages = 0
        max_pages = max(1, (max_items + page_size - 1) // page_size)
        last_error = ""

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                while pages < max_pages and len(articles) < max_items:
                    page_params = dict(params)
                    if next_page:
                        page_params["page"] = next_page
                    response = await client.get(
                        _NEWSDATA_BASE,
                        params=page_params,
                        headers={"User-Agent": "AIContentPlatform/1.0"},
                    )
                    # Free plan rejects size>10 — retry once with size=10.
                    if response.status_code >= 400 and page_params.get("size", 0) > _FREE_PAGE_SIZE:
                        logger.warning(
                            "NewsData rejected size=%s (status=%s); retrying with size=%s",
                            page_params.get("size"),
                            response.status_code,
                            _FREE_PAGE_SIZE,
                        )
                        page_params["size"] = _FREE_PAGE_SIZE
                        params["size"] = _FREE_PAGE_SIZE
                        page_size = _FREE_PAGE_SIZE
                        response = await client.get(
                            _NEWSDATA_BASE,
                            params=page_params,
                            headers={"User-Agent": "AIContentPlatform/1.0"},
                        )

                    if response.status_code >= 400:
                        try:
                            last_error = response.json().get("message") or response.text[:300]
                        except Exception:
                            last_error = response.text[:300]
                        logger.error(
                            "NewsData API error status=%s body=%s params=%s",
                            response.status_code,
                            last_error,
                            {k: v for k, v in page_params.items() if k != "apikey"},
                        )
                        break

                    data = response.json()
                    status = str(data.get("status") or "").lower()
                    if status and status not in {"success", "ok"}:
                        last_error = str(data.get("message") or data.get("results") or status)
                        logger.error("NewsData API logical failure: %s", last_error)
                        break

                    results = data.get("results", [])
                    if not isinstance(results, list) or not results:
                        break
                    for item in results:
                        if len(articles) >= max_items:
                            break
                        article = _item_to_article(item)
                        if article is not None:
                            articles.append(article)
                    next_page = data.get("nextPage")
                    pages += 1
                    if not next_page:
                        break
        except httpx.HTTPError as exc:
            logger.error("NewsData API fetch failed: %s", exc)
            return articles
        except Exception:
            logger.exception("NewsData returned unexpected response")
            return articles

        logger.info(
            "NewsData connector fetched %d articles "
            "(max_items=%d pages=%d query=%r categories=%s error=%r)",
            len(articles),
            max_items,
            pages,
            query or "(latest)",
            categories or [],
            last_error or None,
        )
        return articles


def _item_to_article(item: dict) -> NormalizedArticle | None:
    url = item.get("link", "")
    if not url:
        return None
    category = normalize_category(item.get("category"))
    tags = item.get("keywords") or item.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    published_at = _parse_newsdata_date(item.get("pubDate", ""))
    description = (item.get("description") or "").strip() or None
    content = (item.get("content") or "").strip() or None
    # Free NewsData plans often return a paywall stub instead of full body.
    if content and "ONLY AVAILABLE IN PAID" in content.upper():
        content = description
    body_text = content or description
    return NormalizedArticle(
        title=item.get("title", ""),
        url=url,
        summary=description,
        body_text=body_text,
        published_at=published_at,
        author=_join_creators(item.get("creator")),
        raw_payload={
            **item,
            "category": category,
            "tags": list(tags) if isinstance(tags, list) else [],
        },
    )


def _parse_newsdata_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _join_creators(creators: list[str] | str | None) -> str | None:
    if not creators:
        return None
    if isinstance(creators, list):
        return ", ".join(creators)
    return str(creators)
