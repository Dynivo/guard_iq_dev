"""Compose Knowledge Engine with strategies, filter, policy, and caches."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.infrastructure.local_retrieval import (
    InMemoryVectorStore,
    LocalEmbeddingProvider,
)
from app.modules.ai_cache.application.namespaced import NamespacedAICache, RetrievalCache
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.context.application.builder import DefaultContextBuilder
from app.modules.context.application.token_budget import DefaultTokenBudgetManager
from app.modules.knowledge.application.compressor import ExtractiveCompressor
from app.modules.knowledge.application.engine import DefaultKnowledgeEngine
from app.modules.knowledge.application.filter import DefaultKnowledgeFilter
from app.modules.knowledge.application.query_planner import DefaultQueryPlanner
from app.modules.knowledge.application.ranker import HeuristicRanker
from app.modules.knowledge.application.retriever import StrategyRetriever
from app.modules.knowledge.application.strategies import (
    GraphRetrievalStrategy,
    HybridRetrievalStrategy,
    KeywordRetrievalStrategy,
    MetadataRetrievalStrategy,
    SemanticRetrievalStrategy,
)
from app.modules.knowledge.domain.models import SearchMode
from app.modules.knowledge.infrastructure.policy_loader import YamlKnowledgePolicyLoader
from app.modules.knowledge.infrastructure.sources.base import (
    CompositeKnowledgeSource,
    InMemoryKnowledgeSource,
    StaticBrandSource,
)
from app.modules.brand_intelligence.infrastructure.brand_memory_source import BrandMemorySource
from app.modules.knowledge.infrastructure.sources.pg_sources import (
    PgArticleSource,
    PgClaimSource,
    PgDraftSource,
    PgExampleSource,
    PgPreferenceSource,
    PgRuleSource,
)

_CONFIGS = Path(__file__).resolve().parents[4] / "configs" / "knowledge"


def _build_strategies(source, embeddings, vector_store):
    keyword = KeywordRetrievalStrategy(source)
    metadata = MetadataRetrievalStrategy(source)
    semantic = SemanticRetrievalStrategy(
        source=source, embeddings=embeddings, vector_store=vector_store
    )
    hybrid = HybridRetrievalStrategy(
        keyword=keyword, semantic=semantic, metadata=metadata
    )
    return {
        SearchMode.KEYWORD: keyword,
        SearchMode.METADATA: metadata,
        SearchMode.SEMANTIC: semantic,
        SearchMode.HYBRID: hybrid,
        SearchMode.GRAPH: GraphRetrievalStrategy(),
    }


class KnowledgeEngineFactory:
    @staticmethod
    def create_memory(
        source: InMemoryKnowledgeSource | None = None,
        *,
        policy_id: str = "default",
    ) -> DefaultKnowledgeEngine:
        policy = YamlKnowledgePolicyLoader(_CONFIGS).load(policy_id)
        src = source or InMemoryKnowledgeSource()
        composite = CompositeKnowledgeSource([StaticBrandSource(), src])
        vectors = InMemoryVectorStore()
        embeddings = LocalEmbeddingProvider()
        strategies = _build_strategies(composite, embeddings, vectors)
        planner = DefaultQueryPlanner(policy)
        ns_cache = NamespacedAICache(InMemoryAICache())
        retriever = StrategyRetriever(
            strategies,
            planner=planner,
            retrieval_cache=RetrievalCache(ns_cache),
        )
        return DefaultKnowledgeEngine(
            retriever=retriever,
            ranker=HeuristicRanker(policy),
            knowledge_filter=DefaultKnowledgeFilter(),
            compressor=ExtractiveCompressor(),
            context_builder=DefaultContextBuilder(DefaultTokenBudgetManager()),
            query_planner=planner,
            policy=policy,
        )

    @staticmethod
    def create(
        session: AsyncSession | None = None,
        *,
        policy_id: str = "default",
    ) -> DefaultKnowledgeEngine:
        if session is None:
            return KnowledgeEngineFactory.create_memory(policy_id=policy_id)
        policy = YamlKnowledgePolicyLoader(_CONFIGS).load(policy_id)
        sources = CompositeKnowledgeSource(
            [
                BrandMemorySource(session),
                StaticBrandSource(session),
                PgArticleSource(session),
                PgExampleSource(session),
                PgRuleSource(session),
                PgClaimSource(session),
                PgPreferenceSource(session),
                PgDraftSource(session),
            ]
        )
        vectors = InMemoryVectorStore()
        embeddings = LocalEmbeddingProvider()
        strategies = _build_strategies(sources, embeddings, vectors)
        planner = DefaultQueryPlanner(policy)
        ns_cache = NamespacedAICache(InMemoryAICache())
        retriever = StrategyRetriever(
            strategies,
            planner=planner,
            retrieval_cache=RetrievalCache(ns_cache),
        )
        return DefaultKnowledgeEngine(
            retriever=retriever,
            ranker=HeuristicRanker(policy),
            knowledge_filter=DefaultKnowledgeFilter(),
            compressor=ExtractiveCompressor(),
            context_builder=DefaultContextBuilder(DefaultTokenBudgetManager()),
            query_planner=planner,
            policy=policy,
        )
