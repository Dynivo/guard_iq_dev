"""Knowledge source backed by finalized Brand Memory vector chunks / DNA."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brand_intelligence.infrastructure.postgres.repositories import (
    PgBrandMemoryRepository,
    PgBrandProfileRepository,
    PgBrandVectorChunkRepository,
    PgNeverSayRepository,
)
from app.modules.knowledge.domain.models import KnowledgeItem, KnowledgeQuery, KnowledgeType


class BrandMemorySource:
    """Selective Brand Memory context — prefers chunk text, never dumps full DNA blindly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profiles = PgBrandProfileRepository(session)
        self._memories = PgBrandMemoryRepository(session)
        self._chunks = PgBrandVectorChunkRepository(session)
        self._never_say = PgNeverSayRepository(session)

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        if not query.include_brand or query.organization_id is None:
            return []
        org_id = query.organization_id
        profile = await self._profiles.get_default(org_id)
        if not profile:
            return []
        memory = await self._memories.get_active(org_id, profile.id)
        if not memory or memory.lifecycle.value != "finalized":
            return []

        items: list[KnowledgeItem] = []
        q = (query.query_text or "").lower()
        chunks = await self._chunks.list_for_profile(org_id, profile.id)
        selected = []
        for ch in chunks:
            if not q or any(tok in ch.text.lower() for tok in q.split() if len(tok) > 3):
                selected.append(ch)
        if not selected:
            selected = chunks[:6]
        for i, ch in enumerate(selected[:8]):
            items.append(
                KnowledgeItem(
                    id=f"brand-memory:{profile.id}:{ch.section}:{i}",
                    type=KnowledgeType.BRAND,
                    organization_id=org_id,
                    title=f"Brand Memory — {ch.section}",
                    content=ch.text[:4000],
                    source_quality=0.92,
                    confidence=memory.confidence,
                    reliability=0.9,
                    freshness=0.9,
                    authority=0.9,
                    organization_relevance=1.0,
                    created_at=datetime.now(timezone.utc),
                    source_name="brand_memory",
                )
            )

        never = await self._never_say.get(org_id, profile.id)
        if never and (never.forbidden or never.never_use or never.discouraged):
            lines = [
                "Never-Say Policy:",
                f"Forbidden: {', '.join(never.forbidden[:40])}",
                f"Never use: {', '.join(never.never_use[:40])}",
                f"Discouraged: {', '.join(never.discouraged[:40])}",
            ]
            items.append(
                KnowledgeItem(
                    id=f"brand-memory:{profile.id}:never-say",
                    type=KnowledgeType.BRAND,
                    organization_id=org_id,
                    title="Never-Say / Compliance Vocabulary",
                    content="\n".join(lines),
                    source_quality=0.98,
                    confidence=1.0,
                    reliability=0.98,
                    freshness=1.0,
                    authority=1.0,
                    organization_relevance=1.0,
                    created_at=datetime.now(timezone.utc),
                    source_name="brand_never_say",
                )
            )
        return items
