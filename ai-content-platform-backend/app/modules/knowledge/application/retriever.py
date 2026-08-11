"""Retriever — delegates search to RetrievalStrategy; never ranks."""

from __future__ import annotations

import time
from typing import Mapping

from app.modules.ai_cache.application.namespaced import RetrievalCache
from app.modules.knowledge.domain.models import (
    KnowledgeQuery,
    PlannedQuery,
    RetrievalResult,
    SearchMode,
)
from app.modules.knowledge.domain.ports import RetrievalStrategy
from app.modules.knowledge.application.query_planner import DefaultQueryPlanner


class StrategyRetriever:
    """Resolves RetrievalStrategy by PlannedQuery.search_type."""

    def __init__(
        self,
        strategies: Mapping[SearchMode, RetrievalStrategy],
        *,
        planner: DefaultQueryPlanner | None = None,
        retrieval_cache: RetrievalCache | None = None,
    ) -> None:
        self._strategies = dict(strategies)
        self._planner = planner or DefaultQueryPlanner()
        self._cache = retrieval_cache

    async def retrieve(
        self, query: KnowledgeQuery, *, planned: PlannedQuery | None = None
    ) -> RetrievalResult:
        started = time.perf_counter()
        plan = planned or self._planner.plan(query)
        mode = plan.search_type

        cache_key = {
            "org": str(query.organization_id),
            "q": query.query_text,
            "mode": mode.value,
            "depth": plan.search_depth,
            "filters": plan.filters,
        }
        if self._cache is not None:
            hit = await self._cache.get(cache_key)
            if hit and "item_ids" in hit:
                # Cache stores serialized thin payload; miss rebuild via strategy
                pass  # Prefer live strategy for correctness of item bodies in M5 refinement

        strategy = self._strategies.get(mode)
        if strategy is None and mode == SearchMode.GRAPH:
            strategy = self._strategies.get(SearchMode.GRAPH)
        if strategy is None:
            # Fallback hybrid
            strategy = self._strategies.get(SearchMode.HYBRID)
        if strategy is None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return RetrievalResult(items=(), mode=mode, duration_ms=duration_ms)

        items = await strategy.search(query, planned=plan)
        duration_ms = int((time.perf_counter() - started) * 1000)

        if self._cache is not None:
            await self._cache.set(
                cache_key,
                {
                    "item_ids": [i.id for i in items],
                    "count": len(items),
                    "mode": mode.value,
                },
            )

        return RetrievalResult(
            items=items, mode=mode, duration_ms=duration_ms, cache_hit=False
        )


# Back-compat alias used by older imports
DefaultHybridRetriever = StrategyRetriever
