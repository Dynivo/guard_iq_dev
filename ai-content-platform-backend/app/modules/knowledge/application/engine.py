"""Knowledge Engine facade."""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.modules.context.application.builder import DefaultContextBuilder
from app.modules.context.domain.models import ContextBuildInput
from app.modules.context.domain.ports import ContextBuilder
from app.modules.knowledge.application.query_planner import DefaultQueryPlanner
from app.modules.knowledge.domain.models import (
    CompressedKnowledge,
    FilteredKnowledge,
    KnowledgeItem,
    KnowledgePolicy,
    KnowledgeQuery,
    KnowledgeType,
    OptimizedContext,
    PlannedQuery,
    RankedKnowledge,
    RetrievalResult,
)
from app.modules.knowledge.domain.ports import (
    KnowledgeCompressor,
    KnowledgeFilter,
    Ranker,
    Retriever,
)

logger = get_logger(__name__)


class DefaultKnowledgeEngine:
    def __init__(
        self,
        *,
        retriever: Retriever,
        ranker: Ranker,
        knowledge_filter: KnowledgeFilter,
        compressor: KnowledgeCompressor,
        context_builder: ContextBuilder | None = None,
        query_planner: DefaultQueryPlanner | None = None,
        policy: KnowledgePolicy | None = None,
    ) -> None:
        self._retriever = retriever
        self._ranker = ranker
        self._filter = knowledge_filter
        self._compressor = compressor
        self._context = context_builder or DefaultContextBuilder()
        self._policy = policy or KnowledgePolicy()
        self._planner = query_planner or DefaultQueryPlanner(self._policy)

    async def plan(self, query: KnowledgeQuery) -> PlannedQuery:
        return self._planner.plan(query)

    async def retrieve(
        self, query: KnowledgeQuery, *, planned: PlannedQuery | None = None
    ) -> RetrievalResult:
        return await self._retriever.retrieve(query, planned=planned)

    async def rank(
        self, items: tuple[KnowledgeItem, ...], query: KnowledgeQuery
    ) -> RankedKnowledge:
        return await self._ranker.rank(items, query)

    async def filter(
        self, ranked: RankedKnowledge, query: KnowledgeQuery
    ) -> FilteredKnowledge:
        return await self._filter.filter(ranked, query, self._policy)

    async def compress(
        self, filtered: FilteredKnowledge, *, token_budget: int
    ) -> CompressedKnowledge:
        return await self._compressor.compress(filtered, token_budget=token_budget)

    async def prepare_context(self, query: KnowledgeQuery) -> OptimizedContext:
        started = time.perf_counter()
        planned = await self.plan(query)
        retrieval = await self.retrieve(query, planned=planned)
        ranked = await self.rank(retrieval.items, query)
        filtered = await self.filter(ranked, query)
        compressed = await self.compress(filtered, token_budget=query.token_budget)

        brand = self._join_type(compressed.items, KnowledgeType.BRAND)
        examples = self._join_type(compressed.items, KnowledgeType.EXAMPLE)
        rules = self._join_type(compressed.items, KnowledgeType.RULE)
        claims = self._join_type(compressed.items, KnowledgeType.CLAIM)
        prefs = self._join_type(compressed.items, KnowledgeType.PREFERENCE)
        skip = {
            KnowledgeType.BRAND,
            KnowledgeType.EXAMPLE,
            KnowledgeType.RULE,
            KnowledgeType.CLAIM,
            KnowledgeType.PREFERENCE,
        }
        other = tuple(i for i in compressed.items if i.type not in skip)
        compressed_other = CompressedKnowledge(
            items=other,
            tokens_before=compressed.tokens_before,
            tokens_after=compressed.tokens_after,
            duration_ms=compressed.duration_ms,
        )

        ctx = await self._context.build(
            ContextBuildInput(
                query=query,
                compressed=compressed_other,
                brand_text=brand,
                examples_text=examples,
                rules_text=rules,
                claims_text=claims,
                preferences_text=prefs,
            )
        )
        metrics = {
            **ctx.metrics,
            "retrieval_ms": retrieval.duration_ms,
            "ranking_ms": ranked.duration_ms,
            "filter_ms": filtered.duration_ms,
            "filtered_dropped": filtered.dropped_count,
            "drop_reasons": filtered.drop_reasons,
            "compression_ms": compressed.duration_ms,
            "total_ms": int((time.perf_counter() - started) * 1000),
            "candidate_count": len(retrieval.items),
            "ranked_count": len(ranked.items),
            "filtered_count": len(filtered.items),
            "compressed_count": len(compressed.items),
            "search_type": planned.search_type.value,
            "policy_id": planned.policy_id,
            "correlation_id": query.correlation_id,
        }
        logger.info(
            "knowledge.prepare_context",
            extra={
                "app_module": "knowledge",
                "operation": "prepare_context",
                "correlation_id": query.correlation_id,
                "outcome": "success",
                "duration_ms": metrics["total_ms"],
            },
        )
        return OptimizedContext(
            text=ctx.text,
            citations=ctx.citations,
            citation_map=ctx.citation_map,
            knowledge_sources=ctx.knowledge_sources,
            items=ctx.items,
            token_estimate=ctx.token_estimate,
            token_budget=ctx.token_budget,
            sections=ctx.sections,
            metrics=metrics,
        )

    @staticmethod
    def _join_type(items: tuple[KnowledgeItem, ...], ktype: KnowledgeType) -> str:
        parts = [i.content for i in items if i.type == ktype]
        return "\n".join(parts)
