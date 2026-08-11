"""SQLAlchemy-backed knowledge sources."""

from __future__ import annotations

import uuid
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.intelligence import Claim
from app.infrastructure.postgres.models.learning import Example, Rule, WritingPreference
from app.infrastructure.postgres.models.news import Article
from app.modules.knowledge.domain.models import KnowledgeItem, KnowledgeQuery, KnowledgeType


class PgArticleSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        stmt = (
            select(Article)
            .where(Article.organization_id == query.organization_id)
            .order_by(Article.created_at.desc())
            .limit(query.top_k)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        q = query.query_text.lower()
        items = []
        for r in rows:
            blob = f"{r.title} {r.summary or ''} {r.body_text or ''}"
            if q and q not in blob.lower() and query.search_mode.value == "keyword":
                continue
            items.append(
                KnowledgeItem(
                    id=str(r.id),
                    type=KnowledgeType.ARTICLE,
                    organization_id=r.organization_id,
                    title=r.title,
                    content=(r.summary or r.body_text or "")[:4000],
                    metadata={"status": r.status},
                    source_quality=0.7,
                    reliability=0.7,
                    authority=0.6,
                    organization_relevance=1.0,
                    created_at=r.created_at,
                    source_name="articles",
                )
            )
        return items


class PgExampleSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        if not query.include_examples:
            return []
        stmt = (
            select(Example)
            .where(Example.organization_id == query.organization_id, Example.is_active.is_(True))
            .order_by(Example.weight.desc())
            .limit(10)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            KnowledgeItem(
                id=str(r.id),
                type=KnowledgeType.EXAMPLE,
                organization_id=r.organization_id,
                title=r.hook or "Example",
                content=r.text,
                metadata={"weight": r.weight},
                source_quality=min(1.0, 0.5 + (r.weight or 0) / 10.0),
                reliability=min(1.0, 0.5 + (r.weight or 0) / 10.0),
                authority=0.7,
                organization_relevance=1.0,
                created_at=r.created_at,
                source_name="examples",
            )
            for r in rows
        ]


class PgRuleSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        if not query.include_rules:
            return []
        stmt = (
            select(Rule)
            .where(Rule.organization_id == query.organization_id, Rule.is_active.is_(True))
            .order_by(Rule.priority.desc())
            .limit(30)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            KnowledgeItem(
                id=str(r.id),
                type=KnowledgeType.RULE,
                organization_id=r.organization_id,
                title=r.category,
                content=r.text,
                metadata={"priority": r.priority},
                source_quality=0.9,
                reliability=0.9,
                authority=0.95,
                organization_relevance=1.0,
                created_at=r.created_at,
                source_name="rules",
            )
            for r in rows
        ]


class PgClaimSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        if not query.include_claims:
            return []
        stmt = (
            select(Claim)
            .where(Claim.organization_id == query.organization_id)
            .order_by(Claim.created_at.desc())
            .limit(20)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            KnowledgeItem(
                id=str(r.id),
                type=KnowledgeType.CLAIM,
                organization_id=r.organization_id,
                title="Claim",
                content=r.text,
                metadata={"provenance": r.provenance, "source_type": r.source_type},
                source_quality=float(r.confidence or 0.85),
                confidence=float(r.confidence or 0.85),
                reliability=float(r.confidence or 0.85),
                authority=0.8,
                organization_relevance=1.0,
                created_at=r.created_at,
                source_name="claims",
            )
            for r in rows
        ]


class PgPreferenceSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        if not query.include_preferences:
            return []
        stmt = (
            select(WritingPreference)
            .where(
                WritingPreference.organization_id == query.organization_id,
                WritingPreference.is_active.is_(True),
            )
            .limit(20)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            KnowledgeItem(
                id=str(r.id),
                type=KnowledgeType.PREFERENCE,
                organization_id=r.organization_id,
                title=r.category,
                content=r.preference,
                metadata={"confidence": r.confidence},
                source_quality=float(r.confidence or 0.5),
                confidence=float(r.confidence or 0.5),
                reliability=float(r.confidence or 0.5),
                authority=0.7,
                organization_relevance=1.0,
                created_at=r.created_at,
                source_name="preferences",
            )
            for r in rows
        ]


class PgDraftSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        stmt = (
            select(Draft)
            .where(Draft.organization_id == query.organization_id)
            .order_by(Draft.created_at.desc())
            .limit(10)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        items = []
        for r in rows:
            ktype = (
                KnowledgeType.APPROVED_POST
                if getattr(r, "status", "") == "approved"
                else KnowledgeType.DRAFT
            )
            body = r.edited_text or r.generated_text or ""
            items.append(
                KnowledgeItem(
                    id=str(r.id),
                    type=ktype,
                    organization_id=r.organization_id,
                    title=r.hook or "Draft",
                    content=str(body)[:4000],
                    metadata={"status": r.status},
                    source_quality=0.8 if ktype == KnowledgeType.APPROVED_POST else 0.5,
                    reliability=0.8 if ktype == KnowledgeType.APPROVED_POST else 0.5,
                    authority=0.6,
                    organization_relevance=1.0,
                    created_at=r.created_at,
                    source_name="drafts",
                )
            )
        return items
