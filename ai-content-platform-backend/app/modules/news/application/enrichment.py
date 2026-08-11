"""Enrichment helpers — attach entities/events/opportunities/taxonomy to articles."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.modules.news.domain.models import CanonicalArticle


def with_metadata(article: CanonicalArticle, **updates: Any) -> CanonicalArticle:
    md = dict(article.metadata)
    md.update(updates)
    return replace(article, metadata=md)


def with_category_tags(
    article: CanonicalArticle, *, category: str, tags: tuple[str, ...]
) -> CanonicalArticle:
    return replace(
        article,
        category=category or article.category,
        tags=tags or article.tags,
    )
