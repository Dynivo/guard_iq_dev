"""Retrieval strategies — Retriever delegates search here."""

from __future__ import annotations

from app.modules.knowledge.domain.models import (
    KnowledgeItem,
    KnowledgeQuery,
    KnowledgeType,
    PlannedQuery,
    SearchMode,
)
from app.modules.knowledge.domain.ports import (
    EmbeddingProvider,
    KnowledgeSource,
    RetrievalStrategy,
    VectorStore,
)


def _enrich_from_payload(
    *,
    doc_id: str,
    hit: dict,
    query: KnowledgeQuery,
    by_id: dict[str, KnowledgeItem],
) -> KnowledgeItem | None:
    payload = hit.get("payload") or {}
    base = by_id.get(doc_id)
    score = float(hit.get("score") or 0.0)
    if base:
        return base.with_updates(similarity=score)
    if not payload.get("content"):
        return None
    return KnowledgeItem(
        id=doc_id,
        type=KnowledgeType(payload.get("type", "document")),
        organization_id=query.organization_id,
        title=str(payload.get("title") or doc_id),
        content=str(payload.get("content")),
        metadata=dict(payload),
        source_quality=float(payload.get("source_quality", 0.5)),
        reliability=float(payload.get("reliability", payload.get("source_quality", 0.5))),
        confidence=float(payload.get("confidence", 0.5)),
        authority=float(payload.get("authority", 0.5)),
        organization_relevance=float(payload.get("organization_relevance", 1.0)),
        similarity=score,
        source_name=str(payload.get("source_name") or "vector"),
    )


def _source_meta(filters: dict) -> dict:
    return {
        k: v
        for k, v in filters.items()
        if k not in {"organization_id", "allowed_types", "allowed_languages"}
    }


class KeywordRetrievalStrategy:
    def __init__(self, source: KnowledgeSource) -> None:
        self._source = source

    async def search(
        self, query: KnowledgeQuery, *, planned: PlannedQuery
    ) -> tuple[KnowledgeItem, ...]:
        keyword_query = KnowledgeQuery(
            organization_id=query.organization_id,
            query_text=query.query_text,
            correlation_id=query.correlation_id,
            types=query.types,
            search_mode=SearchMode.KEYWORD,
            top_k=planned.search_depth,
            token_budget=query.token_budget,
            metadata_filters=_source_meta({**planned.filters, **query.metadata_filters}),
            include_brand=query.include_brand,
            include_examples=query.include_examples,
            include_rules=query.include_rules,
            include_claims=query.include_claims,
            include_preferences=query.include_preferences,
            policy_id=query.policy_id,
        )
        items = await self._source.fetch(keyword_query)
        return tuple(items[: planned.search_depth * 2])


class MetadataRetrievalStrategy:
    def __init__(self, source: KnowledgeSource) -> None:
        self._source = source

    async def search(
        self, query: KnowledgeQuery, *, planned: PlannedQuery
    ) -> tuple[KnowledgeItem, ...]:
        meta = _source_meta({**planned.filters, **query.metadata_filters})
        meta_query = KnowledgeQuery(
            organization_id=query.organization_id,
            query_text="",
            correlation_id=query.correlation_id,
            types=query.types,
            search_mode=SearchMode.METADATA,
            top_k=planned.search_depth,
            token_budget=query.token_budget,
            metadata_filters=meta,
            include_brand=query.include_brand,
            include_examples=query.include_examples,
            include_rules=query.include_rules,
            include_claims=query.include_claims,
            include_preferences=query.include_preferences,
            policy_id=query.policy_id,
        )
        items = await self._source.fetch(meta_query)
        return tuple(items[: planned.search_depth * 2])


class SemanticRetrievalStrategy:
    def __init__(
        self,
        *,
        source: KnowledgeSource,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._source = source
        self._embeddings = embeddings
        self._vectors = vector_store

    async def search(
        self, query: KnowledgeQuery, *, planned: PlannedQuery
    ) -> tuple[KnowledgeItem, ...]:
        source_items = await self._source.fetch(
            KnowledgeQuery(
                organization_id=query.organization_id,
                query_text=query.query_text,
                correlation_id=query.correlation_id,
                types=query.types,
                search_mode=SearchMode.HYBRID,
                top_k=planned.search_depth,
                token_budget=query.token_budget,
                metadata_filters={
                    k: v
                    for k, v in query.metadata_filters.items()
                    if k
                    not in {"organization_id", "allowed_types", "allowed_languages"}
                },
                include_brand=query.include_brand,
                include_examples=query.include_examples,
                include_rules=query.include_rules,
                include_claims=query.include_claims,
                include_preferences=query.include_preferences,
                policy_id=query.policy_id,
            )
        )
        by_id = {i.id: i for i in source_items}
        emb = await self._embeddings.embed(query.query_text)
        filters = {
            k: v
            for k, v in planned.filters.items()
            if k not in {"allowed_types", "allowed_languages"}
        }
        collection = planned.collections[0] if planned.collections else "knowledge"
        hits = await self._vectors.search(
            collection,
            emb.vector,
            planned.search_depth,
            filters=filters,
        )
        out: list[KnowledgeItem] = []
        for hit in hits:
            item = _enrich_from_payload(
                doc_id=str(hit.get("id")),
                hit=hit,
                query=query,
                by_id=by_id,
            )
            if item:
                out.append(item)
        return tuple(out)


class HybridRetrievalStrategy:
    def __init__(
        self,
        *,
        keyword: RetrievalStrategy,
        semantic: RetrievalStrategy,
        metadata: RetrievalStrategy | None = None,
    ) -> None:
        self._keyword = keyword
        self._semantic = semantic
        self._metadata = metadata

    async def search(
        self, query: KnowledgeQuery, *, planned: PlannedQuery
    ) -> tuple[KnowledgeItem, ...]:
        keyword_items = await self._keyword.search(query, planned=planned)
        semantic_items = await self._semantic.search(query, planned=planned)
        merged: dict[str, KnowledgeItem] = {}
        for item in keyword_items:
            merged[item.id] = item
        for item in semantic_items:
            existing = merged.get(item.id)
            if existing is None or (item.similarity or 0) > (existing.similarity or 0):
                merged[item.id] = item
        if self._metadata and query.metadata_filters:
            for item in await self._metadata.search(query, planned=planned):
                merged.setdefault(item.id, item)
        return tuple(list(merged.values())[: planned.search_depth * 2])


class GraphRetrievalStrategy:
    """Future graph retrieval — stub returns empty until graph store lands."""

    async def search(
        self, query: KnowledgeQuery, *, planned: PlannedQuery
    ) -> tuple[KnowledgeItem, ...]:
        return ()
