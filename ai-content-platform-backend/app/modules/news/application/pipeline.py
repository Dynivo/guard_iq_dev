"""News Intelligence Pipeline — normalize → dedupe → cluster → topic → score → enrich → store."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.modules.news.application.cluster import DefaultClusterAnalyzer, DefaultClusterEngine
from app.modules.news.application.deduplicator import InMemoryDeduplicator
from app.modules.news.application.enrichment import with_category_tags, with_metadata
from app.modules.news.application.sentiment import analyze_sentiment
from app.modules.news.application.entity_extractor import DefaultEntityExtractor
from app.modules.news.application.event_detector import DefaultEventDetector
from app.modules.news.application.metrics import NewsMetricsRecorder
from app.modules.news.application.normalizer import (
    DefaultContentValidator,
    DefaultFeedValidator,
    DefaultNormalizer,
)
from app.modules.news.application.opportunity_detector import DefaultOpportunityDetector
from app.modules.news.application.reputation import DefaultSourceReputationEngine
from app.modules.news.application.resilience import (
    InMemoryCircuitBreaker,
    InMemoryHealthMonitor,
    InMemoryRateLimitManager,
)
from app.modules.news.application.scorer import DeterministicNewsScorer
from app.modules.news.application.source_learning import SourceLearningEngine
from app.modules.news.application.story_timeline import DefaultStoryTimelineBuilder
from app.modules.news.application.taxonomy import DefaultTaxonomyAssigner, YamlTaxonomyLoader
from app.modules.news.application.topic_intelligence import DefaultTopicIntelligence
from app.modules.news.application.trend_engine import DefaultTrendEngine
from app.modules.news.domain.models import (
    ArticleCluster,
    CanonicalArticle,
    NewsPolicy,
    NewsScore,
    NormalizedArticle,
    PipelineResult,
    SourceDefinition,
    TopicSignals,
)
from app.modules.news.domain.ports import ConnectorRegistry

_NEWS = Path(__file__).resolve().parents[4] / "configs" / "news"


class DefaultNewsPipeline:
    def __init__(
        self,
        *,
        connectors: ConnectorRegistry,
        normalizer: DefaultNormalizer | None = None,
        deduplicator: InMemoryDeduplicator | None = None,
        cluster_engine: DefaultClusterEngine | None = None,
        topic: DefaultTopicIntelligence | None = None,
        scorer: DeterministicNewsScorer | None = None,
        policy: NewsPolicy | None = None,
        brand_terms: list[str] | None = None,
        exclude_terms: list[str] | None = None,
        health: InMemoryHealthMonitor | None = None,
        rate_limiter: InMemoryRateLimitManager | None = None,
        circuit_breaker: InMemoryCircuitBreaker | None = None,
        metrics: NewsMetricsRecorder | None = None,
        store: Any | None = None,
        config_dir: Path | None = None,
        entity_extractor: DefaultEntityExtractor | None = None,
        event_detector: DefaultEventDetector | None = None,
        opportunity_detector: DefaultOpportunityDetector | None = None,
        trend_engine: DefaultTrendEngine | None = None,
        story_timeline: DefaultStoryTimelineBuilder | None = None,
        taxonomy_assigner: DefaultTaxonomyAssigner | None = None,
        source_learning: SourceLearningEngine | None = None,
    ) -> None:
        root = config_dir or _NEWS
        self._connectors = connectors
        self._normalizer = normalizer or DefaultNormalizer()
        self._dedupe = deduplicator or InMemoryDeduplicator()
        self._cluster = cluster_engine or DefaultClusterEngine()
        self._topic = topic or DefaultTopicIntelligence()
        self._scorer = scorer or DeterministicNewsScorer()
        self._policy = policy or NewsPolicy()
        self._brand_terms = list(brand_terms or [])
        self._exclude_terms = list(exclude_terms or [])
        self._health = health or InMemoryHealthMonitor()
        self._rate = rate_limiter or InMemoryRateLimitManager()
        self._circuit = circuit_breaker or InMemoryCircuitBreaker()
        self._metrics = metrics or NewsMetricsRecorder()
        self._feed_validator = DefaultFeedValidator()
        self._content_validator = DefaultContentValidator()
        self._reputation = DefaultSourceReputationEngine()
        self._cluster_analyzer = DefaultClusterAnalyzer()
        self._store = store
        self._entities = entity_extractor or DefaultEntityExtractor()
        self._events = event_detector or DefaultEventDetector(root)
        self._opportunities = opportunity_detector or DefaultOpportunityDetector(root)
        self._trends = trend_engine or DefaultTrendEngine()
        self._timelines = story_timeline or DefaultStoryTimelineBuilder()
        self._taxonomy = taxonomy_assigner or DefaultTaxonomyAssigner(
            YamlTaxonomyLoader(root / "taxonomy" / "default.yaml")
        )
        self._learning = source_learning or SourceLearningEngine()
        self._last_topics: list[TopicSignals] = []
        self._last_scores: list[NewsScore] = []

    async def run(
        self,
        source: SourceDefinition,
        *,
        organization_id: uuid.UUID | None = None,
        items: list[NormalizedArticle] | None = None,
    ) -> PipelineResult:
        errors: list[str] = []
        org_id = organization_id or (
            uuid.UUID(source.organization_id)
            if source.organization_id
            else uuid.UUID(int=0)
        )
        key = f"{source.connector_type}:{source.source_id}"

        if not self._circuit.allow(key):
            return PipelineResult(
                source_id=source.source_id,
                errors=("circuit open",),
                metrics={"circuit": "open"},
            )
        if not self._rate.allow(key):
            return PipelineResult(
                source_id=source.source_id,
                errors=("rate limited",),
                metrics={"rate_limited": True},
            )

        started = time.perf_counter()
        raw_items: list[NormalizedArticle] = list(items or [])
        if items is None:
            try:
                connector = self._connectors.get(source.connector_type)
                ok_cfg, cfg_err = True, ""
                if hasattr(connector, "validate_config"):
                    ok_cfg, cfg_err = await connector.validate_config(source.config)
                if not ok_cfg:
                    errors.append(cfg_err or "invalid connector config")
                    self._circuit.record_failure(key)
                    self._health.record_failure(source.source_id, cfg_err)
                    self._metrics.record_fetch(ok=False)
                    return PipelineResult(
                        source_id=source.source_id, errors=tuple(errors)
                    )
                raw_items = await connector.fetch(source.config)
                self._rate.record(key)
            except Exception as exc:  # noqa: BLE001
                latency = (time.perf_counter() - started) * 1000
                self._circuit.record_failure(key)
                self._health.record_failure(source.source_id, str(exc))
                self._metrics.record_fetch(ok=False, latency_ms=latency)
                return PipelineResult(
                    source_id=source.source_id,
                    errors=(str(exc),),
                    metrics={"fetch_failed": True},
                )

        latency = (time.perf_counter() - started) * 1000
        self._circuit.record_success(key)
        self._health.record_success(source.source_id, latency)
        self._metrics.record_fetch(ok=True, latency_ms=latency)

        valid_raw, feed_errors = self._feed_validator.validate_items(raw_items)
        errors.extend(feed_errors)

        normalized: list[CanonicalArticle] = []
        for item in valid_raw:
            art = self._normalizer.normalize(
                item, source=source, organization_id=org_id
            )
            ok, err = self._content_validator.validate(art)
            if not ok:
                errors.append(err)
                continue
            normalized.append(art)

        unique: list[CanonicalArticle] = []
        duplicates = 0
        for art in normalized:
            if await self._dedupe.is_duplicate(
                org_id, art.canonical_url or art.url, art.content_hash
            ):
                duplicates += 1
                continue
            if any(
                self._dedupe.is_near_duplicate(
                    art, other, threshold=self._policy.title_similarity_threshold
                )
                for other in unique
            ):
                duplicates += 1
                continue
            unique.append(art)
            await self._dedupe.mark_seen(org_id, art.canonical_url or art.url)
            if hasattr(self._dedupe, "mark_hash"):
                self._dedupe.mark_hash(org_id, art.content_hash)

        self._metrics.record_duplicates(duplicates)
        self._metrics.record_processed(len(unique))

        clusters = self._cluster.cluster(unique, policy=self._policy)
        self._metrics.record_clusters(len(clusters))
        cluster_stats = self._cluster_analyzer.analyze(clusters)
        cluster_by_url = _index_clusters(clusters)

        topics: list[TopicSignals] = []
        scores: list[NewsScore] = []
        for art in unique:
            topic = self._topic.analyze(art, policy=self._policy)
            topics.append(topic)
            score = self._scorer.score(
                art,
                topic=topic,
                source=source,
                policy=self._policy,
                brand_terms=self._brand_terms,
                exclude_terms=self._exclude_terms,
            )
            scores.append(score)
            self._metrics.record_score(score.composite)

        self._last_topics = topics
        self._last_scores = scores

        # Enrichment: entities → events → opportunities → trends → timeline → taxonomy
        enriched: list[CanonicalArticle] = []
        events_by_url: dict[str, list[str]] = {}
        opportunities_meta: list[dict] = []
        for art, topic, score in zip(unique, topics, scores, strict=False):
            entities = self._entities.extract(art, topic=topic)
            detected = self._events.detect(art, topic=topic)
            event_types = [e.event_type for e in detected]
            url = art.canonical_url or art.url
            events_by_url[url] = event_types
            cluster = cluster_by_url.get(url)
            opps = self._opportunities.detect(
                art,
                topic=topic,
                score=score,
                cluster=cluster,
                events=event_types,
            )
            opportunities_meta.append(opps.to_dict())
            tax = self._taxonomy.assign(art, topic=topic, entities=entities)
            sentiment = analyze_sentiment(art)
            art2 = with_metadata(
                art,
                entities=entities.to_dict(),
                events=[e.to_dict() for e in detected],
                opportunities=opps.to_dict(),
                taxonomy=tax.to_dict(),
                sentiment=sentiment.to_dict(),
            )
            art2 = with_category_tags(
                art2,
                category=tax.topic or art2.category,
                tags=tax.tags or art2.tags,
            )
            enriched.append(art2)

        trend_metrics = self._trends.observe_batch(enriched, topics)
        timelines = self._timelines.build(
            clusters, enriched, events_by_url=events_by_url
        )
        for tl in timelines:
            for u in tl.article_urls:
                for i, art in enumerate(enriched):
                    if (art.canonical_url or art.url) == u:
                        enriched[i] = with_metadata(
                            art, story_timeline=tl.to_dict()
                        )

        self._learning.store.upsert_source(source)

        stored = 0
        if self._store is not None:
            for art in enriched:
                await self._store.save_canonical(art, org_id, source)
                stored += 1

        health = self._health.get(source.source_id)
        rep = self._learning.reputation(source)
        return PipelineResult(
            source_id=source.source_id,
            fetched=len(raw_items),
            normalized=len(normalized),
            duplicates=duplicates,
            clustered=len(clusters),
            scored=len(scores),
            stored=stored,
            articles=tuple(enriched),
            clusters=tuple(clusters),
            scores=tuple(scores),
            metrics={
                "latency_ms": latency,
                "cluster_stats": cluster_stats,
                "reputation": rep,
                "health": asdict(health),
                "pipeline": self._metrics.snapshot(),
                "topics": [t.to_dict() for t in topics],
                "opportunities": opportunities_meta,
                "trends": [t.to_dict() for t in trend_metrics],
                "story_timelines": [t.to_dict() for t in timelines],
                "entities_stored": len(self._entities.store.all()),
                "ready_for_knowledge": True,
            },
            errors=tuple(errors),
        )


def _index_clusters(clusters: list[ArticleCluster]) -> dict[str, ArticleCluster]:
    out: dict[str, ArticleCluster] = {}
    for c in clusters:
        for u in c.article_urls:
            out[u] = c
    return out
