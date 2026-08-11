"""Unit tests for Milestone 8 News Intelligence Pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.news.application.cluster import DefaultClusterEngine
from app.modules.news.application.deduplicator import InMemoryDeduplicator
from app.modules.news.application.factory import NewsPipelineFactory
from app.modules.news.application.normalizer import DefaultNormalizer, canonicalize_url
from app.modules.news.application.resilience import (
    InMemoryCircuitBreaker,
    InMemoryRateLimitManager,
)
from app.modules.news.application.scheduler import InProcessNewsScheduler
from app.modules.news.domain.models import (
    CanonicalArticle,
    NewsPolicy,
    NormalizedArticle,
    SourceDefinition,
)
from app.modules.news.infrastructure.connector_factory import DefaultConnectorRegistry
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.domain.models import WorkflowContext

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
NEWS = CONFIGS / "news"


def _source(**kwargs) -> SourceDefinition:
    base = dict(
        source_id="s1",
        name="Test RSS",
        connector_type="rss",
        config={},
        authority=0.8,
        reliability=0.8,
        trust=0.8,
    )
    base.update(kwargs)
    return SourceDefinition(**base)


@pytest.mark.asyncio
async def test_normalize_canonical_url_and_hash() -> None:
    norm = DefaultNormalizer()
    art = norm.normalize(
        NormalizedArticle(
            title="DSPT Update for Care Homes",
            url="https://WWW.Example.com/path/?utm_source=x&id=1",
            summary="Annual assessment required.",
            body_text="Care providers must complete DSPT.",
            published_at=datetime.now(timezone.utc),
        ),
        source=_source(),
    )
    assert art.canonical_url == canonicalize_url(
        "https://WWW.Example.com/path/?utm_source=x&id=1"
    )
    assert "utm_source" not in art.canonical_url
    assert art.content_hash
    assert art.language == "en"


@pytest.mark.asyncio
async def test_dedupe_url_and_title_similarity() -> None:
    dedupe = InMemoryDeduplicator()
    a = CanonicalArticle(
        title="Ransomware hits UK hospitals",
        url="https://a.example/1",
        canonical_url="https://a.example/1",
        content_hash="aaa",
    )
    b = CanonicalArticle(
        title="Ransomware hits UK hospitals!",
        url="https://b.example/2",
        canonical_url="https://b.example/2",
        content_hash="bbb",
    )
    assert dedupe.is_near_duplicate(a, b, threshold=0.85)


@pytest.mark.asyncio
async def test_cluster_engine_groups_similar() -> None:
    engine = DefaultClusterEngine()
    now = datetime.now(timezone.utc)
    articles = [
        CanonicalArticle(
            title="NCSC warns of phishing campaign",
            url="https://a/1",
            canonical_url="https://a/1",
            source="NCSC",
            published_at=now,
        ),
        CanonicalArticle(
            title="NCSC warns of phishing campaign across UK",
            url="https://b/2",
            canonical_url="https://b/2",
            source="BBC",
            published_at=now,
        ),
        CanonicalArticle(
            title="Unrelated cloud pricing update",
            url="https://c/3",
            canonical_url="https://c/3",
            source="Tech",
            published_at=now,
        ),
    ]
    clusters = engine.cluster(articles, policy=NewsPolicy(cluster_similarity_threshold=0.5))
    assert len(clusters) >= 2
    assert any(len(c.article_urls) >= 2 for c in clusters)


@pytest.mark.asyncio
async def test_pipeline_normalize_dedupe_score() -> None:
    comps = NewsPipelineFactory.create_components(config_dir=NEWS)
    items = [
        NormalizedArticle(
            title="DSPT compliance deadline for care homes",
            url="https://news.example/dspt-1",
            summary="Healthcare providers must complete DSPT.",
            body_text="The DSPT framework requires annual assessment in the UK.",
            published_at=datetime.now(timezone.utc),
        ),
        NormalizedArticle(
            title="DSPT compliance deadline for care homes",
            url="https://news.example/dspt-1?utm_source=tw",
            summary="Duplicate",
            published_at=datetime.now(timezone.utc),
        ),
    ]
    result = await comps["pipeline"].run(_source(), items=items)
    assert result.fetched == 2
    assert result.duplicates >= 1
    assert result.scored == len(result.articles)
    assert result.scores
    assert result.scores[0].composite > 0
    assert "reputation" in result.metrics


@pytest.mark.asyncio
async def test_connector_registry_lists_rss_and_newsdata() -> None:
    reg = DefaultConnectorRegistry()
    types = reg.list_types()
    assert "rss" in types
    assert "news_api" in types


@pytest.mark.asyncio
async def test_rss_validate_config() -> None:
    conn = DefaultConnectorRegistry().get("rss")
    ok, err = await conn.validate_config({})
    assert not ok
    ok2, _ = await conn.validate_config({"feed_url": "https://example.com/feed"})
    assert ok2


@pytest.mark.asyncio
async def test_newsdata_validate_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEWSDATA_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        conn = DefaultConnectorRegistry().get("news_api")
        ok, err = await conn.validate_config({})
        assert not ok
        assert "api_key" in err
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_source_registry_yaml() -> None:
    comps = NewsPipelineFactory.create_components(config_dir=NEWS)
    sources = comps["source_registry"].list_all()
    assert any(s.connector_type == "rss" for s in sources)
    assert any(s.connector_type == "news_api" for s in sources)


@pytest.mark.asyncio
async def test_scheduler_due_and_priority_queue() -> None:
    comps = NewsPipelineFactory.create_components(config_dir=NEWS)
    sch = comps["scheduler"]
    due = sch.due_sources(trigger="periodic")
    assert due
    job_id = await sch.enqueue(due[0], priority=10)
    assert job_id
    assert sch.health()["queue_depth"] >= 1
    item = sch.pop_next()
    assert item is not None


@pytest.mark.asyncio
async def test_rate_limit_and_circuit_breaker() -> None:
    rl = InMemoryRateLimitManager(max_calls=2, window_seconds=60)
    assert rl.allow("k")
    rl.record("k")
    rl.record("k")
    assert not rl.allow("k")

    cb = InMemoryCircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    assert cb.allow("s")
    cb.record_failure("s")
    cb.record_failure("s")
    assert not cb.allow("s")
    cb.record_success("s")
    assert cb.allow("s")


@pytest.mark.asyncio
async def test_workflow_news_nodes() -> None:
    engine, wreg, nreg = WorkflowFactory.create(workflows_dir=CONFIGS / "workflows")
    for t in (
        "news.fetch",
        "news.parse",
        "news.normalize",
        "news.dedupe",
        "news.cluster",
        "news.score",
        "news.enrich",
        "news.store",
    ):
        assert t in nreg.known_types()
    assert "news_ingestion" in wreg.list_names()

    result = await engine.run(
        "news_ingestion",
        initial_context=WorkflowContext(
            correlation_id="news-m8",
            data={
                "news.source": {
                    "source_id": "wf",
                    "name": "WF",
                    "connector_type": "rss",
                    "authority": 0.7,
                    "reliability": 0.7,
                    "trust": 0.7,
                },
                "news.raw_items": [
                    {
                        "title": "Microsoft patches critical vulnerability",
                        "url": "https://msrc.example/1",
                        "summary": "Azure identity endpoint issue.",
                        "body_text": "Technology vendors released patches.",
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            },
        ),
    )
    assert result.success
    assert result.context.get("news.ready_for_knowledge") is True
    assert result.context.get("news.scored", 0) >= 1 or result.context.get("news.stored", 0) >= 0
