"""News module use cases: list/get articles, list/create sources, run source ingest."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.infrastructure.connectors.registry import get_connector, list_connector_types
from app.modules.news.infrastructure.repositories import (
    PgArticleRepository,
    PgNewsSourceRepository,
)

logger = get_logger(__name__)


async def _check_configured(connector_type: str, config: dict) -> tuple[bool, str | None]:
    """Run the connector's own validate_config to see if it's ready to fetch."""
    try:
        connector = get_connector(connector_type)
    except ValueError as exc:
        return False, str(exc)
    try:
        ok, error = await connector.validate_config(config or {})
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return ok, (error or None) if not ok else None


class ListArticlesUseCase:
    """Return a paginated list of articles for the org."""

    def __init__(self, article_repo: PgArticleRepository) -> None:
        self._repo = article_repo

    async def execute(
        self,
        org_id: uuid.UUID,
        status: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        articles = await self._repo.list_by_org(
            org_id, status=status, category=category, limit=limit, offset=offset
        )
        total = await self._repo.count_by_org(org_id, status=status, category=category)
        source_names = await self._repo.source_names_for(
            org_id, [a.source_id for a in articles]
        )
        return {
            "items": [_article_to_dict(a, source_names.get(a.source_id)) for a in articles],
            "total": total,
            "limit": limit,
            "offset": offset,
            "category": category,
        }


class ListArticleCategoriesUseCase:
    """Return distinct article categories for the org."""

    def __init__(self, article_repo: PgArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, org_id: uuid.UUID) -> dict[str, Any]:
        categories = await self._repo.list_categories(org_id)
        return {"items": categories, "total": len(categories)}


class GetArticleUseCase:
    """Return a single article by ID."""

    def __init__(self, article_repo: PgArticleRepository) -> None:
        self._repo = article_repo

    async def execute(self, org_id: uuid.UUID, article_id: uuid.UUID) -> dict[str, Any]:
        article = await self._repo.get_by_id(article_id, org_id)
        if article is None:
            raise NotFoundError("Article", str(article_id))
        names = await self._repo.source_names_for(org_id, [article.source_id])
        return _article_to_dict(article, names.get(article.source_id))


class ListSourcesUseCase:
    """Return all news sources for the org."""

    def __init__(self, source_repo: PgNewsSourceRepository) -> None:
        self._repo = source_repo

    async def execute(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        sources = await self._repo.list_by_org(org_id)
        result = []
        for s in sources:
            cfg = s.config_json if isinstance(s.config_json, dict) else {}
            is_configured, config_error = await _check_configured(s.connector_type, cfg)
            result.append(_source_to_dict(s, is_configured=is_configured, config_error=config_error))
        return result


class CreateSourceUseCase:
    """Create a new news source."""

    def __init__(self, source_repo: PgNewsSourceRepository) -> None:
        self._repo = source_repo

    async def execute(
        self,
        org_id: uuid.UUID,
        name: str,
        connector_type: str,
        config_json: dict,
        schedule_cron: str | None = None,
        *,
        category: str | None = None,
        credibility_score: int | None = None,
        priority: int | None = None,
        api_key_name: str | None = None,
    ) -> dict[str, Any]:
        valid_types = list_connector_types()
        if connector_type not in valid_types:
            raise ValidationError(
                f"Invalid connector_type '{connector_type}'. Valid: {', '.join(valid_types)}"
            )
        source = await self._repo.create(
            org_id=org_id,
            name=name,
            connector_type=connector_type,
            config_json=config_json,
            schedule_cron=schedule_cron,
            category=category,
            credibility_score=credibility_score,
            priority=priority,
            api_key_name=api_key_name,
        )
        logger.info("Created news source: name=%s type=%s org=%s", name, connector_type, org_id)
        is_configured, config_error = await _check_configured(connector_type, config_json)
        return _source_to_dict(source, is_configured=is_configured, config_error=config_error)


class UpdateSourceUseCase:
    """Update an existing news source (name, config, schedule, enabled)."""

    def __init__(self, source_repo: PgNewsSourceRepository) -> None:
        self._repo = source_repo

    async def execute(
        self,
        org_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        name: str | None = None,
        config_json: dict | None = None,
        schedule_cron: str | None = None,
        enabled: bool | None = None,
        category: str | None = None,
        credibility_score: int | None = None,
        priority: int | None = None,
    ) -> dict[str, Any]:
        source = await self._repo.update(
            source_id,
            org_id,
            name=name,
            config_json=config_json,
            schedule_cron=schedule_cron,
            enabled=enabled,
            category=category,
            credibility_score=credibility_score,
            priority=priority,
        )
        if source is None:
            raise NotFoundError("NewsSource", str(source_id))
        logger.info("Updated news source: id=%s org=%s", source_id, org_id)
        cfg = source.config_json if isinstance(source.config_json, dict) else {}
        is_configured, config_error = await _check_configured(source.connector_type, cfg)
        return _source_to_dict(source, is_configured=is_configured, config_error=config_error)


def _article_to_dict(a: Any, source_name: str | None = None) -> dict[str, Any]:
    from app.modules.news.application.category_utils import normalize_category

    score = a.score_json if isinstance(getattr(a, "score_json", None), dict) else {}
    meta = a.metadata_json if isinstance(getattr(a, "metadata_json", None), dict) else {}
    nested_meta = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    sentiment = score.get("sentiment") or nested_meta.get("sentiment") or meta.get("sentiment")
    taxonomy = nested_meta.get("taxonomy") or meta.get("taxonomy") or {}
    trend_keys: list[str] = []
    if isinstance(taxonomy, dict):
        for key in ("topic", "industry", "framework", "subtopic"):
            val = taxonomy.get(key)
            if val:
                trend_keys.append(str(val).lower())
    return {
        "id": str(a.id),
        "organization_id": str(a.organization_id),
        "source_id": str(a.source_id),
        "source_name": source_name,
        "title": a.title,
        "summary": a.summary,
        "url": a.url,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "author": a.author,
        "status": a.status,
        "category": normalize_category(getattr(a, "category", None)),
        "tags": getattr(a, "tags", None) or [],
        "language": getattr(a, "language", None),
        "relevance_score": score.get("composite") or score.get("relevance"),
        "ai_relevance": score.get("ai_relevance"),
        "admin_override": score.get("admin_override"),
        "score_json": score or None,
        "sentiment": sentiment,
        "trend_keys": trend_keys,
        "created_at": a.created_at.isoformat(),
    }


def _source_to_dict(
    s: Any, *, is_configured: bool = True, config_error: str | None = None
) -> dict[str, Any]:
    health = s.health_json if isinstance(getattr(s, "health_json", None), dict) else {}
    credibility = getattr(s, "credibility_score", None)
    if credibility is None and getattr(s, "authority", None) is not None:
        credibility = int(round(float(s.authority) * 100))
    cfg = s.config_json if isinstance(s.config_json, dict) else {}
    return {
        "id": str(s.id),
        "organization_id": str(s.organization_id),
        "name": s.name,
        "category": getattr(s, "category", None) or cfg.get("category"),
        "connector_type": s.connector_type,
        "config_json": cfg,
        "rss_url": cfg.get("feed_url"),
        "api_endpoint": cfg.get("api_endpoint"),
        "api_key_name": getattr(s, "api_key_name", None) or cfg.get("api_key_name"),
        "schedule_cron": s.schedule_cron,
        "enabled": s.enabled,
        "is_configured": is_configured,
        "config_error": config_error,
        "credibility_score": credibility,
        "priority": getattr(s, "priority", None),
        "authority": getattr(s, "authority", None),
        "reliability": getattr(s, "reliability", None),
        "trust": getattr(s, "trust", None),
        "health": {
            "circuit_state": getattr(s, "circuit_state", None) or health.get("circuit_state"),
            "failure_rate": getattr(s, "failure_rate", None),
            "last_error": getattr(s, "last_error", None),
            "healthy": bool(
                (getattr(s, "circuit_state", None) or "closed").lower()
                in {"closed", "", "none"}
            )
            and not (getattr(s, "last_error", None) and (getattr(s, "failure_rate", 0) or 0) > 0.5),
        },
        "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
        "created_at": s.created_at.isoformat(),
    }
