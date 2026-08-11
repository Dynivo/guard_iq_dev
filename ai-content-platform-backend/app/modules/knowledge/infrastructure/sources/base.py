"""In-memory / session knowledge sources for modular retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.domain.models import KnowledgeItem, KnowledgeQuery, KnowledgeType
from app.modules.organization.application.client_profile import (
    load_client_profile,
    read_file_fallback_profile,
)

_BRAND_DIR = Path(__file__).resolve().parents[5] / "configs" / "brand"


class StaticBrandSource:
    """Brand / client profile knowledge. Prefers org DB profile when session is set."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        if not query.include_brand:
            return []
        if self._session is not None and query.organization_id is not None:
            text = await load_client_profile(self._session, query.organization_id)
        else:
            path = _BRAND_DIR / "client-profile.md"
            text = path.read_text(encoding="utf-8") if path.exists() else read_file_fallback_profile()
            if text == "No client profile configured.":
                text = "No brand profile."
        return [
            KnowledgeItem(
                id="brand:client-profile",
                type=KnowledgeType.BRAND,
                organization_id=query.organization_id,
                title="Brand / Client Profile",
                content=text[:8000],
                source_quality=0.95,
                confidence=1.0,
                reliability=0.95,
                freshness=1.0,
                authority=0.95,
                organization_relevance=1.0,
                created_at=datetime.now(timezone.utc),
                source_name="brand",
            )
        ]


class InMemoryKnowledgeSource:
    """Test/demo source holding arbitrary items."""

    def __init__(self, items: list[KnowledgeItem] | None = None) -> None:
        self._items = list(items or [])

    def add(self, item: KnowledgeItem) -> None:
        self._items.append(item)

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        results = []
        q = query.query_text.lower()
        for item in self._items:
            if item.organization_id and item.organization_id != query.organization_id:
                continue
            if query.types and item.type not in query.types:
                continue
            if query.metadata_filters:
                if any(item.metadata.get(k) != v for k, v in query.metadata_filters.items()):
                    continue
            if q and q not in item.content.lower() and q not in item.title.lower():
                # keyword miss — still include for hybrid/semantic merge paths
                if query.search_mode.value in {"keyword", "metadata"}:
                    continue
            results.append(item)
        return results


class CompositeKnowledgeSource:
    def __init__(self, sources: list) -> None:
        self._sources = list(sources)

    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]:
        out: list[KnowledgeItem] = []
        for src in self._sources:
            out.extend(await src.fetch(query))
        return out
