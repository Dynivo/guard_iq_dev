"""Unit tests for M8 News Pipeline refinements (ADR 0042)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.modules.news.application.entity_extractor import DefaultEntityExtractor
from app.modules.news.application.event_detector import DefaultEventDetector
from app.modules.news.application.factory import NewsPipelineFactory
from app.modules.news.application.opportunity_detector import DefaultOpportunityDetector
from app.modules.news.application.source_learning import SourceLearningEngine
from app.modules.news.application.story_timeline import DefaultStoryTimelineBuilder
from app.modules.news.application.taxonomy import DefaultTaxonomyAssigner, YamlTaxonomyLoader
from app.modules.news.application.trend_engine import DefaultTrendEngine
from app.modules.news.domain.models import (
    ArticleCluster,
    CanonicalArticle,
    NewsScore,
    NormalizedArticle,
    OpportunityType,
    SourceDefinition,
    SourceFeedbackEvent,
    SourceFeedbackKind,
    TopicSignals,
)
from app.modules.workflow.application.factory import WorkflowFactory
from app.modules.workflow.domain.models import WorkflowContext

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
NEWS = CONFIGS / "news"


def _source(**kwargs) -> SourceDefinition:
    base = dict(
        source_id="learn-src",
        name="Learning Source",
        connector_type="rss",
        config={},
        authority=0.5,
        reliability=0.5,
        trust=0.5,
    )
    base.update(kwargs)
    return SourceDefinition(**base)


def _article(**kwargs) -> CanonicalArticle:
    base = dict(
        title="Title",
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        summary="",
        body_text="",
        content_hash="h1",
    )
    base.update(kwargs)
    return CanonicalArticle(**base)


@pytest.mark.asyncio
async def test_opportunity_types_without_content_generation() -> None:
    detector = DefaultOpportunityDetector(NEWS)
    art = _article(
        title="DSPT compliance checklist for care homes",
        summary="Best practice guidance and how to prepare.",
        url="https://example.com/dspt",
        canonical_url="https://example.com/dspt",
    )
    topic = TopicSignals(
        framework="dspt", industry="healthcare", urgency=0.7, business_impact=0.6
    )
    score = NewsScore(composite=0.7, confidence=0.8)
    opps = detector.detect(art, topic=topic, score=score, events=["compliance"])
    assert OpportunityType.COMPLIANCE_UPDATE.value in opps.types
    assert OpportunityType.CHECKLIST.value in opps.types
    # Metadata enrichment only — no body/content field produced
    assert "content" not in opps.to_dict()
    assert "body" not in opps.to_dict()
    assert opps.types


@pytest.mark.asyncio
async def test_entities_and_cves_stored_separately() -> None:
    extractor = DefaultEntityExtractor()
    art = _article(
        title="Microsoft patches CVE-2024-12345 in Azure",
        summary="Cloud identity endpoint vulnerability.",
        body_text="Healthcare orgs using Azure should apply the patch.",
        url="https://example.com/cve",
        canonical_url="https://example.com/cve",
    )
    topic = TopicSignals(technology="azure", industry="healthcare", company="microsoft")
    entities = extractor.extract(art, topic=topic)
    assert "CVE-2024-12345" in entities.cves
    assert "microsoft" in entities.companies or "azure" in entities.technologies
    stored = extractor.store.list_for_url(art.canonical_url)
    assert any(r.entity_type == "cve" and "CVE-2024" in r.value for r in stored)
    assert entities.to_dict()["cves"]


@pytest.mark.asyncio
async def test_events_detected_from_fixture() -> None:
    detector = DefaultEventDetector(NEWS)
    art = _article(
        title="Hospital data breach exposes records",
        summary="Incident caused by ransomware vulnerability.",
        body_text="A serious data breach and outage disrupted care.",
        url="https://example.com/breach",
        canonical_url="https://example.com/breach",
    )
    events = detector.detect(art)
    types = {e.event_type for e in events}
    assert "breach" in types
    assert detector.store.list_for_url(art.canonical_url)


@pytest.mark.asyncio
async def test_trend_metrics_update_across_batch() -> None:
    engine = DefaultTrendEngine()
    topic = TopicSignals(industry="healthcare", framework="dspt")
    batch1 = [
        _article(url=f"https://e/{i}", canonical_url=f"https://e/{i}", title=f"DSPT {i}")
        for i in range(3)
    ]
    m1 = engine.observe_batch(batch1, [topic] * 3)
    assert m1
    assert any(t.topic_key == "healthcare" for t in m1)
    batch2 = [
        _article(url=f"https://e2/{i}", canonical_url=f"https://e2/{i}", title=f"More {i}")
        for i in range(5)
    ]
    m2 = engine.observe_batch(batch2, [topic] * 5)
    health = next(t for t in m2 if t.topic_key == "healthcare")
    assert health.article_count == 5
    assert health.growth != 0 or health.velocity != 0
    assert "predicted_trend" in health.to_dict()


@pytest.mark.asyncio
async def test_story_timeline_orders_cluster_members() -> None:
    now = datetime.now(timezone.utc)
    arts = [
        _article(
            title="Update 2",
            url="https://t/2",
            canonical_url="https://t/2",
            published_at=now,
        ),
        _article(
            title="Update 1",
            url="https://t/1",
            canonical_url="https://t/1",
            published_at=now - timedelta(hours=2),
        ),
    ]
    # Force a cluster with both URLs
    cluster = ArticleCluster(
        cluster_id="c1",
        label="Story",
        article_urls=("https://t/2", "https://t/1"),
        cohesion=0.9,
    )
    timelines = DefaultStoryTimelineBuilder().build(
        [cluster],
        arts,
        events_by_url={"https://t/1": ["breach"], "https://t/2": ["patch_release"]},
    )
    assert len(timelines) == 1
    assert timelines[0].article_urls == ("https://t/1", "https://t/2")
    assert "breach" in timelines[0].events


@pytest.mark.asyncio
async def test_taxonomy_path_from_yaml() -> None:
    assigner = DefaultTaxonomyAssigner(
        YamlTaxonomyLoader(NEWS / "taxonomy" / "default.yaml")
    )
    art = _article(
        title="NHS care homes ransomware advisory",
        summary="Healthcare security update for ransomware.",
        body_text="healthcare ransomware",
    )
    topic = TopicSignals(industry="healthcare", category="security", threat="ransomware")
    path = assigner.assign(art, topic=topic)
    assert path.industry == "healthcare"
    assert path.topic
    assert path.to_dict()["industry"] == "healthcare"


@pytest.mark.asyncio
async def test_source_learning_updates_reputation() -> None:
    engine = SourceLearningEngine(alpha=0.2)
    src = _source()
    before = src.authority
    updated = engine.apply(
        src,
        SourceFeedbackEvent(
            source_id=src.source_id,
            kind=SourceFeedbackKind.APPROVAL,
            weight=1.0,
        ),
    )
    assert updated.authority > before
    assert engine.store.list_events(src.source_id)
    rejected = engine.apply(
        updated,
        SourceFeedbackEvent(
            source_id=src.source_id,
            kind=SourceFeedbackKind.REJECTION,
            weight=1.0,
        ),
    )
    assert rejected.authority < updated.authority


@pytest.mark.asyncio
async def test_pipeline_enrichment_ready_for_knowledge() -> None:
    pipe = NewsPipelineFactory.create_memory(config_dir=NEWS)
    result = await pipe.run(
        _source(source_id="pipe-enrich"),
        items=[
            NormalizedArticle(
                title="CVE-2024-99999 zero-day vulnerability advisory",
                url="https://pipe.example/1",
                summary="Microsoft Azure patch for healthcare compliance DSPT.",
                body_text="Security advisory and checklist for best practice guidance.",
                published_at=datetime.now(timezone.utc),
            )
        ],
    )
    assert result.scored >= 1
    assert result.metrics.get("ready_for_knowledge") is True
    assert result.articles
    art = result.articles[0]
    assert "entities" in art.metadata
    assert "opportunities" in art.metadata
    assert "taxonomy" in art.metadata
    # Opportunity detector never generates content body
    opps = art.metadata["opportunities"]
    assert "types" in opps
    assert "generated_content" not in opps


@pytest.mark.asyncio
async def test_workflow_includes_enrich_node() -> None:
    engine, wreg, nreg = WorkflowFactory.create(workflows_dir=CONFIGS / "workflows")
    assert "news.enrich" in nreg.known_types()
    result = await engine.run(
        "news_ingestion",
        initial_context=WorkflowContext(
            correlation_id="news-m8r",
            data={
                "news.source": {
                    "source_id": "wf-r",
                    "name": "WF",
                    "connector_type": "rss",
                    "authority": 0.7,
                    "reliability": 0.7,
                    "trust": 0.7,
                },
                "news.raw_items": [
                    {
                        "title": "Microsoft patches critical vulnerability CVE-2024-1111",
                        "url": "https://msrc.example/r1",
                        "summary": "Azure identity endpoint issue for healthcare.",
                        "body_text": "Technology vendors released patches and compliance guidance.",
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            },
        ),
    )
    assert result.success
    assert result.context.get("news.enriched") is True
    assert result.context.get("news.ready_for_knowledge") is True
