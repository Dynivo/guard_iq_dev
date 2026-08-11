"""Intelligence module repositories — persistence for embeddings and relevance scores."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.intelligence import ArticleEmbedding, RelevanceScore


class PgArticleEmbeddingRepository:
    """Postgres repository for article embeddings metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        article_id: uuid.UUID,
        model_version: str,
        qdrant_id: str | None,
        dimensions: int,
    ) -> ArticleEmbedding:
        embedding = ArticleEmbedding(
            article_id=article_id,
            model_version=model_version,
            qdrant_id=qdrant_id,
            dimensions=dimensions,
        )
        self._session.add(embedding)
        await self._session.flush()
        return embedding

    async def get_by_article(self, article_id: uuid.UUID) -> ArticleEmbedding | None:
        stmt = select(ArticleEmbedding).where(ArticleEmbedding.article_id == article_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class PgRelevanceScoreRepository:
    """Postgres repository for relevance scores."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        article_id: uuid.UUID,
        organization_id: uuid.UUID,
        score: int,
        sector: str | None = None,
        framework: str | None = None,
        audience: str | None = None,
        angle: str | None = None,
        reason: str | None = None,
        prompt_version: str | None = None,
    ) -> RelevanceScore:
        record = RelevanceScore(
            article_id=article_id,
            organization_id=organization_id,
            score=score,
            sector=sector,
            framework=framework,
            audience=audience,
            angle=angle,
            reason=reason,
            prompt_version=prompt_version,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_latest_for_article(
        self, article_id: uuid.UUID
    ) -> RelevanceScore | None:
        stmt = (
            select(RelevanceScore)
            .where(RelevanceScore.article_id == article_id)
            .order_by(RelevanceScore.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
