"""Knowledge Engine ports."""

from __future__ import annotations

from typing import Protocol

from app.modules.knowledge.domain.models import (
    CompressedKnowledge,
    EmbeddingResult,
    FilteredKnowledge,
    KnowledgeItem,
    KnowledgePolicy,
    KnowledgeQuery,
    OptimizedContext,
    PlannedQuery,
    RankedKnowledge,
    RetrievalResult,
)


class KnowledgeSource(Protocol):
    async def fetch(self, query: KnowledgeQuery) -> list[KnowledgeItem]: ...


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> EmbeddingResult: ...

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]: ...


class VectorStore(Protocol):
    async def upsert(
        self, collection: str, doc_id: str, vector: list[float], payload: dict
    ) -> None: ...

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        *,
        filters: dict | None = None,
    ) -> list[dict]: ...


class KnowledgePolicyLoader(Protocol):
    def load(self, policy_id: str = "default") -> KnowledgePolicy: ...


class QueryPlanner(Protocol):
    def plan(self, query: KnowledgeQuery) -> PlannedQuery: ...


class RetrievalStrategy(Protocol):
    async def search(
        self, query: KnowledgeQuery, *, planned: PlannedQuery
    ) -> tuple[KnowledgeItem, ...]: ...


class Retriever(Protocol):
    async def retrieve(
        self, query: KnowledgeQuery, *, planned: PlannedQuery | None = None
    ) -> RetrievalResult: ...


class Ranker(Protocol):
    async def rank(
        self, items: tuple[KnowledgeItem, ...], query: KnowledgeQuery
    ) -> RankedKnowledge: ...


class KnowledgeFilter(Protocol):
    async def filter(
        self,
        ranked: RankedKnowledge,
        query: KnowledgeQuery,
        policy: KnowledgePolicy,
    ) -> FilteredKnowledge: ...


class KnowledgeCompressor(Protocol):
    async def compress(
        self, filtered: FilteredKnowledge, *, token_budget: int
    ) -> CompressedKnowledge: ...


class KnowledgeEngine(Protocol):
    async def prepare_context(self, query: KnowledgeQuery) -> OptimizedContext: ...

    async def plan(self, query: KnowledgeQuery) -> PlannedQuery: ...

    async def retrieve(
        self, query: KnowledgeQuery, *, planned: PlannedQuery | None = None
    ) -> RetrievalResult: ...

    async def rank(
        self, items: tuple[KnowledgeItem, ...], query: KnowledgeQuery
    ) -> RankedKnowledge: ...

    async def filter(
        self, ranked: RankedKnowledge, query: KnowledgeQuery
    ) -> FilteredKnowledge: ...

    async def compress(
        self, filtered: FilteredKnowledge, *, token_budget: int
    ) -> CompressedKnowledge: ...
