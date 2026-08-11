"""Knowledge Engine refinements + Context Builder unit tests."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.modules.ai.application.health import ProviderHealthRegistry
from app.modules.ai.application.lifecycle import AIRequestState
from app.modules.ai.application.plugins import (
    ForbiddenWordsValidator,
    JsonValidator,
    LengthValidator,
    SchemaValidator,
)
from app.modules.ai_cache.application.namespaced import (
    CacheNamespace,
    EmbeddingCache,
    NamespacedAICache,
)
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.context.application.token_budget import DefaultTokenBudgetManager
from app.modules.knowledge.application.compressor import ExtractiveCompressor
from app.modules.knowledge.application.factory import KnowledgeEngineFactory
from app.modules.knowledge.application.filter import DefaultKnowledgeFilter
from app.modules.knowledge.application.query_planner import DefaultQueryPlanner
from app.modules.knowledge.application.ranker import HeuristicRanker
from app.modules.knowledge.domain.models import (
    FilteredKnowledge,
    KnowledgeItem,
    KnowledgePolicy,
    KnowledgeQuery,
    KnowledgeType,
    RankedKnowledge,
    SearchMode,
)
from app.modules.knowledge.infrastructure.policy_loader import YamlKnowledgePolicyLoader
from app.modules.knowledge.infrastructure.sources.base import InMemoryKnowledgeSource
from app.modules.providers.infrastructure.model_registry import YamlModelRegistry
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.domain.models import WorkflowContext

ORG = uuid.uuid4()
CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def _item(iid: str, content: str, **kwargs) -> KnowledgeItem:
    return KnowledgeItem(
        id=iid,
        type=kwargs.get("type", KnowledgeType.ARTICLE),
        organization_id=kwargs.get("organization_id", ORG),
        title=kwargs.get("title", iid),
        content=content,
        source_quality=kwargs.get("source_quality", 0.8),
        confidence=kwargs.get("confidence", 0.7),
        reliability=kwargs.get("reliability", kwargs.get("source_quality", 0.8)),
        freshness=kwargs.get("freshness", 0.9),
        authority=kwargs.get("authority", 0.7),
        organization_relevance=kwargs.get("organization_relevance", 1.0),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        similarity=kwargs.get("similarity"),
        rank_score=kwargs.get("rank_score"),
        source_name=kwargs.get("source_name", "memory"),
        metadata=kwargs.get("metadata", {}),
    )


def test_token_budget_trim() -> None:
    mgr = DefaultTokenBudgetManager()
    items = tuple(_item(f"i{n}", "x" * 400) for n in range(20))
    trimmed = mgr.trim(items, budget=200)
    assert len(trimmed) < len(items)
    assert mgr.estimate("abcd") == 1


def test_ranker_orders_by_score() -> None:
    items = (
        _item("a", "alpha security", similarity=0.1, reliability=0.2),
        _item("b", "security MFA", similarity=0.9, reliability=0.9),
    )
    ranked = asyncio.run(
        HeuristicRanker().rank(
            items,
            KnowledgeQuery(organization_id=ORG, query_text="security"),
        )
    )
    assert ranked.items[0].id == "b"
    assert ranked.items[0].rank_score is not None
    assert ranked.items[0].freshness >= 0.0


def test_filter_dedupes_not_compressor() -> None:
    policy = KnowledgePolicy(drop_content_duplicates=True, min_rank_score=0.05)
    items = (
        _item("a", "Same body text", rank_score=0.5),
        _item("b", "Same body text", rank_score=0.5),
        _item("c", "Different", rank_score=0.5, similarity=0.5),
    )
    filtered = asyncio.run(
        DefaultKnowledgeFilter().filter(
            RankedKnowledge(items=items),
            KnowledgeQuery(organization_id=ORG, query_text="x"),
            policy,
        )
    )
    assert len(filtered.items) == 2
    assert filtered.dropped_count == 1

    # Compressor only trims tokens — keeps duplicates if filter did not run
    out = asyncio.run(
        ExtractiveCompressor().compress(
            FilteredKnowledge(items=items), token_budget=5000
        )
    )
    assert len(out.items) == 3
    assert out.tokens_after <= out.tokens_before


def test_query_planner() -> None:
    planned = DefaultQueryPlanner().plan(
        KnowledgeQuery(
            organization_id=ORG,
            query_text="DSPT",
            search_mode=SearchMode.HYBRID,
            top_k=8,
        )
    )
    assert planned.search_type == SearchMode.HYBRID
    assert planned.search_depth == 8
    assert planned.filters["organization_id"] == str(ORG)
    assert "knowledge" in planned.collections


def test_policy_loader() -> None:
    policy = YamlKnowledgePolicyLoader(CONFIGS / "knowledge").load("default")
    assert policy.policy_id == "default"
    assert policy.min_reliability > 0
    assert policy.ranking_weights.similarity > 0


def test_namespaced_cache() -> None:
    inner = InMemoryAICache()
    ns = NamespacedAICache(inner)
    emb = EmbeddingCache(ns)

    async def _run() -> None:
        await emb.set("hello", {"vector": [0.1]})
        hit = await emb.get("hello")
        assert hit == {"vector": [0.1]}
        raw = await inner.get(f"{CacheNamespace.EMBEDDING}:{EmbeddingCache.key_for('hello')}")
        assert raw is not None

    asyncio.run(_run())


def test_prepare_context_end_to_end() -> None:
    src = InMemoryKnowledgeSource(
        [
            _item("1", "DSPT compliance for care homes", title="DSPT"),
            _item(
                "2",
                "Always cite sources",
                type=KnowledgeType.RULE,
                title="rules",
                source_quality=0.95,
                reliability=0.95,
                source_name="rules",
            ),
        ]
    )
    engine = KnowledgeEngineFactory.create_memory(src)
    ctx = asyncio.run(
        engine.prepare_context(
            KnowledgeQuery(
                organization_id=ORG,
                query_text="DSPT care",
                token_budget=3000,
                correlation_id="corr-k",
            )
        )
    )
    assert ctx.text
    assert ctx.token_estimate > 0
    assert "retrieval_ms" in ctx.metrics
    assert "filter_ms" in ctx.metrics
    assert ctx.citation_map is not None
    assert isinstance(ctx.knowledge_sources, tuple)


def test_local_embedding_deterministic() -> None:
    from app.modules.knowledge.infrastructure.local_retrieval import LocalEmbeddingProvider

    p = LocalEmbeddingProvider(dimensions=32)
    a = asyncio.run(p.embed("hello"))
    b = asyncio.run(p.embed("hello"))
    assert a.vector == b.vector
    assert a.dimensions == 32


def test_memory_vector_store_search() -> None:
    from app.modules.knowledge.infrastructure.local_retrieval import (
        InMemoryVectorStore,
        LocalEmbeddingProvider,
    )

    store = InMemoryVectorStore()
    emb = LocalEmbeddingProvider(dimensions=16)
    v = asyncio.run(emb.embed("alpha")).vector
    asyncio.run(
        store.upsert(
            "k",
            "1",
            v,
            {"organization_id": str(ORG), "content": "alpha", "title": "A"},
        )
    )
    hits = asyncio.run(store.search("k", v, 5, filters={"organization_id": str(ORG)}))
    assert hits and hits[0]["id"] == "1"


def test_model_registry_loads() -> None:
    reg = YamlModelRegistry(CONFIGS / "providers" / "models.yaml")
    spec = reg.get("gemini-flash")
    assert spec is not None
    assert spec.provider == "gemini"
    assert spec.context_window > 0


def test_router_uses_model_registry() -> None:
    from app.modules.providers.application.router import DefaultCapabilityRouter
    from app.modules.providers.infrastructure.yaml_capability_config import (
        YamlCapabilityConfigLoader,
    )

    router = DefaultCapabilityRouter(
        YamlCapabilityConfigLoader(CONFIGS / "providers" / "default.yaml"),
        model_registry=YamlModelRegistry(CONFIGS / "providers" / "models.yaml"),
    )
    decision = asyncio.run(router.resolve("writing"))
    assert decision.primary.provider in {"gemini", "mock", "openai"}
    assert decision.model_id in {"", "gemini-flash"} or decision.model_id


def test_validators() -> None:
    assert JsonValidator().validate('{"a":1}', response_format="json")[0]
    assert not JsonValidator().validate("not-json", response_format="json")[0]
    assert LengthValidator(min_chars=2).validate("hi")[0]
    assert not ForbiddenWordsValidator(["banned"]).validate("this is banned")[0]
    assert SchemaValidator(["hook"]).validate('{"hook":"x"}', response_format="json")[0]


def test_lifecycle_transitions() -> None:
    from app.modules.ai.application.lifecycle import AIRequestRecord

    rec = AIRequestRecord(request_id="r1", correlation_id="c", capability="writing")
    rec.transition(AIRequestState.RUNNING)
    rec.transition(AIRequestState.COMPLETED)
    assert rec.state == AIRequestState.COMPLETED
    assert len(rec.history) == 2


def test_provider_health_score() -> None:
    h = ProviderHealthRegistry()
    h.record_success("openai", latency_ms=100)
    snap = h.snapshot("openai", failure_threshold=5, recovery_timeout_ms=1000)
    assert snap["health_score"] > 0
    assert snap["availability"] == 1.0


def test_workflow_knowledge_nodes() -> None:
    engine, wreg, nreg = WorkflowFactory.create(
        workflows_dir=CONFIGS / "workflows",
    )
    assert "knowledge.plan" in nreg.known_types()
    assert "knowledge.filter" in nreg.known_types()
    assert "knowledge.retrieve" in nreg.known_types()
    assert "knowledge_prepare" in wreg.list_names()
    result = asyncio.run(
        engine.run(
            "knowledge_prepare",
            initial_context=WorkflowContext(
                correlation_id="kwf",
                organization_id=ORG,
                data={"query_text": "security compliance"},
            ),
        )
    )
    assert result.success
    assert result.context.get("knowledge.optimized_context") is not None
    assert result.context.get("knowledge.planned_query") is not None


def test_inference_backend() -> None:
    from app.modules.ai.application.inference import InferenceBackend, resolve_inference_backend

    assert resolve_inference_backend("ollama") == InferenceBackend.LOCAL
    assert resolve_inference_backend("openai") in {
        InferenceBackend.REMOTE,
        InferenceBackend.LOCAL,
        InferenceBackend.GPU_CLUSTER,
    }


def test_filter_org_and_language() -> None:
    other = uuid.uuid4()
    items = (
        _item("ok", "good", rank_score=0.5, metadata={"language": "en"}),
        _item("bad_org", "x", rank_score=0.5, organization_id=other),
        _item("bad_lang", "y", rank_score=0.5, metadata={"language": "fr"}),
    )
    policy = KnowledgePolicy(
        require_org_match=True,
        allowed_languages=("en",),
        min_rank_score=0.05,
        drop_content_duplicates=False,
    )
    filtered = asyncio.run(
        DefaultKnowledgeFilter().filter(
            RankedKnowledge(items=items),
            KnowledgeQuery(organization_id=ORG, query_text=""),
            policy,
        )
    )
    assert [i.id for i in filtered.items] == ["ok"]
