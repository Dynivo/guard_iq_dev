"""Postgres-backed repositories for articles, sources, and deduplication."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.news.application.category_utils import normalize_category
from app.infrastructure.postgres.models.news import (
    Article,
    ArticleRawPayload,
    NewsSource,
    SeenUrl,
)
from app.modules.news.domain.ports import NormalizedArticle
from app.shared.url_utils import hash_content, hash_url, normalize_url


class PgArticleRepository:
    """SQLAlchemy-based article repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        article: NormalizedArticle,
        org_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> uuid.UUID:
        """Persist a normalized article and its raw payload. Returns article id."""
        canonical_url = normalize_url(article.url)
        content_hash = hash_content(article.title) if article.title else None

        db_article = Article(
            organization_id=org_id,
            source_id=source_id,
            title=article.title,
            summary=article.summary,
            body_text=article.body_text,
            url=canonical_url,
            published_at=article.published_at,
            author=article.author,
            normalized_hash=content_hash,
            status="raw",
            language=(article.raw_payload or {}).get("language"),
            category=normalize_category((article.raw_payload or {}).get("category")),
            canonical_url=(article.raw_payload or {}).get("canonical_url") or canonical_url,
            tags=(article.raw_payload or {}).get("tags"),
            topic_json=(article.raw_payload or {}).get("topic_json"),
            score_json=(article.raw_payload or {}).get("score_json"),
            metadata_json=article.raw_payload or None,
        )
        self._session.add(db_article)
        await self._session.flush()

        if article.raw_payload:
            self._session.add(
                ArticleRawPayload(
                    article_id=db_article.id,
                    connector_type="rss",
                    raw_json=article.raw_payload,
                )
            )
            await self._session.flush()

        return db_article.id

    async def update_status(
        self, article_id: uuid.UUID, org_id: uuid.UUID, status: str
    ) -> None:
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.organization_id == org_id)
            .values(status=status)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def exists_by_url(self, org_id: uuid.UUID, url: str) -> bool:
        canonical = normalize_url(url)
        stmt = select(func.count()).where(
            Article.organization_id == org_id,
            Article.url == canonical,
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def get_by_id(
        self, article_id: uuid.UUID, org_id: uuid.UUID
    ) -> Article | None:
        stmt = select(Article).where(
            Article.id == article_id,
            Article.organization_id == org_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        status: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_hidden: bool = False,
    ) -> list[Article]:
        stmt = (
            select(Article)
            .where(Article.organization_id == org_id)
            .order_by(Article.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Article.status == status)
        if category:
            stmt = stmt.where(Article.category == category)
        if not include_hidden:
            stmt = stmt.where(
                func.coalesce(Article.metadata_json["hidden"].astext, "false") != "true"
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_org(
        self,
        org_id: uuid.UUID,
        status: str | None = None,
        category: str | None = None,
        include_hidden: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(Article).where(
            Article.organization_id == org_id
        )
        if status:
            stmt = stmt.where(Article.status == status)
        if category:
            stmt = stmt.where(Article.category == category)
        if not include_hidden:
            stmt = stmt.where(
                func.coalesce(Article.metadata_json["hidden"].astext, "false") != "true"
            )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def set_hidden(
        self, org_id: uuid.UUID, article_id: uuid.UUID, hidden: bool
    ) -> Article | None:
        """Soft-hide/unhide — never touches `status`, so relevant/irrelevant
        classification (and the learning signal it feeds) is unaffected."""
        result = await self._session.execute(
            select(Article).where(Article.id == article_id, Article.organization_id == org_id)
        )
        article = result.scalar_one_or_none()
        if article is None:
            return None
        meta = dict(article.metadata_json or {})
        meta["hidden"] = hidden
        article.metadata_json = meta
        from sqlalchemy.orm import attributes

        attributes.flag_modified(article, "metadata_json")
        return article

    async def list_categories(self, org_id: uuid.UUID) -> list[dict]:
        stmt = (
            select(Article.category, func.count())
            .where(
                Article.organization_id == org_id,
                Article.category.is_not(None),
                Article.category != "",
            )
            .group_by(Article.category)
            .order_by(func.count().desc(), Article.category.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [{"category": name, "count": count} for name, count in rows if name]

    async def source_names_for(
        self, org_id: uuid.UUID, source_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        ids = list({sid for sid in source_ids if sid})
        if not ids:
            return {}
        stmt = select(NewsSource.id, NewsSource.name).where(
            NewsSource.organization_id == org_id,
            NewsSource.id.in_(ids),
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}


class PgNewsSourceRepository:
    """SQLAlchemy-based news source repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, source_id: uuid.UUID, org_id: uuid.UUID
    ) -> NewsSource | None:
        stmt = select(NewsSource).where(
            NewsSource.id == source_id,
            NewsSource.organization_id == org_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: uuid.UUID) -> list[NewsSource]:
        stmt = (
            select(NewsSource)
            .where(NewsSource.organization_id == org_id)
            .order_by(NewsSource.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
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
        authority: float | None = None,
        reliability: float | None = None,
        trust: float | None = None,
        enabled: bool = True,
    ) -> NewsSource:
        cred = credibility_score
        auth = authority
        if cred is not None and auth is None:
            auth = round(max(0, min(100, int(cred))) / 100.0, 4)
        source = NewsSource(
            organization_id=org_id,
            name=name,
            connector_type=connector_type,
            config_json=config_json,
            schedule_cron=schedule_cron,
            enabled=enabled,
            category=category,
            credibility_score=cred,
            priority=priority,
            api_key_name=api_key_name,
            authority=auth,
            reliability=reliability if reliability is not None else auth,
            trust=trust if trust is not None else auth,
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def update(
        self,
        source_id: uuid.UUID,
        org_id: uuid.UUID,
        *,
        name: str | None = None,
        config_json: dict | None = None,
        schedule_cron: str | None = None,
        enabled: bool | None = None,
        category: str | None = None,
        credibility_score: int | None = None,
        priority: int | None = None,
        api_key_name: str | None = None,
    ) -> NewsSource | None:
        source = await self.get_by_id(source_id, org_id)
        if source is None:
            return None
        if name is not None:
            source.name = name
        if config_json is not None:
            source.config_json = config_json
        if schedule_cron is not None:
            source.schedule_cron = schedule_cron or None
        if enabled is not None:
            source.enabled = enabled
        if category is not None:
            source.category = category
        if credibility_score is not None:
            source.credibility_score = credibility_score
            source.authority = round(max(0, min(100, int(credibility_score))) / 100.0, 4)
            source.reliability = source.authority
            source.trust = source.authority
        if priority is not None:
            source.priority = priority
        if api_key_name is not None:
            source.api_key_name = api_key_name
        await self._session.flush()
        return source

    async def update_last_fetched(self, source_id: uuid.UUID) -> None:
        stmt = (
            update(NewsSource)
            .where(NewsSource.id == source_id)
            .values(last_fetched_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)


class PgDeduplicator:
    """URL-based deduplication backed by the seen_urls table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_duplicate(
        self, org_id: uuid.UUID, url: str, content_hash: str | None = None
    ) -> bool:
        url_digest = hash_url(url)
        stmt = select(func.count()).where(
            SeenUrl.organization_id == org_id,
            SeenUrl.url_hash == url_digest,
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def mark_seen(self, org_id: uuid.UUID, url: str) -> None:
        url_digest = hash_url(url)
        canonical = normalize_url(url)
        existing = await self._session.execute(
            select(func.count()).where(
                SeenUrl.organization_id == org_id,
                SeenUrl.url_hash == url_digest,
            )
        )
        if (existing.scalar() or 0) > 0:
            return
        self._session.add(
            SeenUrl(
                organization_id=org_id,
                url_hash=url_digest,
                url=canonical,
            )
        )
        await self._session.flush()
