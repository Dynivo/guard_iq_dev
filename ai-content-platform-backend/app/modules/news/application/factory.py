"""Compose News Intelligence stack."""

from __future__ import annotations

from pathlib import Path

from app.modules.news.application.cluster import DefaultClusterEngine
from app.modules.news.application.deduplicator import InMemoryDeduplicator
from app.modules.news.application.entity_extractor import DefaultEntityExtractor
from app.modules.news.application.event_detector import DefaultEventDetector
from app.modules.news.application.metrics import NewsMetricsRecorder
from app.modules.news.application.normalizer import DefaultNormalizer
from app.modules.news.application.opportunity_detector import DefaultOpportunityDetector
from app.modules.news.application.pipeline import DefaultNewsPipeline
from app.modules.news.application.resilience import (
    InMemoryCircuitBreaker,
    InMemoryHealthMonitor,
    InMemoryRateLimitManager,
)
from app.modules.news.application.scheduler import InProcessNewsScheduler
from app.modules.news.application.scorer import DeterministicNewsScorer
from app.modules.news.application.source_learning import SourceLearningEngine
from app.modules.news.application.source_manager import (
    DefaultSourceManager,
    YamlSourceRegistry,
    load_news_policy,
)
from app.modules.news.application.story_timeline import DefaultStoryTimelineBuilder
from app.modules.news.application.taxonomy import DefaultTaxonomyAssigner, YamlTaxonomyLoader
from app.modules.news.application.topic_intelligence import DefaultTopicIntelligence
from app.modules.news.application.trend_engine import DefaultTrendEngine
from app.modules.news.infrastructure.connector_factory import DefaultConnectorRegistry

_NEWS = Path(__file__).resolve().parents[4] / "configs" / "news"


class NewsPipelineFactory:
    @staticmethod
    def create_memory(
        *,
        config_dir: Path | None = None,
        metrics: NewsMetricsRecorder | None = None,
        brand_terms: list[str] | None = None,
        exclude_terms: list[str] | None = None,
    ) -> DefaultNewsPipeline:
        root = config_dir or _NEWS
        policy = load_news_policy(root)
        learning = SourceLearningEngine()
        return DefaultNewsPipeline(
            connectors=DefaultConnectorRegistry(),
            normalizer=DefaultNormalizer(),
            deduplicator=InMemoryDeduplicator(),
            cluster_engine=DefaultClusterEngine(),
            topic=DefaultTopicIntelligence(),
            scorer=DeterministicNewsScorer(),
            policy=policy,
            brand_terms=brand_terms,
            exclude_terms=exclude_terms,
            health=InMemoryHealthMonitor(),
            rate_limiter=InMemoryRateLimitManager(),
            circuit_breaker=InMemoryCircuitBreaker(),
            metrics=metrics or NewsMetricsRecorder(),
            config_dir=root,
            entity_extractor=DefaultEntityExtractor(),
            event_detector=DefaultEventDetector(root),
            opportunity_detector=DefaultOpportunityDetector(root),
            trend_engine=DefaultTrendEngine(),
            story_timeline=DefaultStoryTimelineBuilder(),
            taxonomy_assigner=DefaultTaxonomyAssigner(
                YamlTaxonomyLoader(root / "taxonomy" / "default.yaml")
            ),
            source_learning=learning,
        )

    @staticmethod
    def create_components(
        *, config_dir: Path | None = None
    ) -> dict:
        root = config_dir or _NEWS
        registry = YamlSourceRegistry(root)
        manager = DefaultSourceManager(registry)
        metrics = NewsMetricsRecorder()
        learning = SourceLearningEngine()
        entities = DefaultEntityExtractor()
        trends = DefaultTrendEngine()
        pipeline = DefaultNewsPipeline(
            connectors=DefaultConnectorRegistry(),
            normalizer=DefaultNormalizer(),
            deduplicator=InMemoryDeduplicator(),
            cluster_engine=DefaultClusterEngine(),
            topic=DefaultTopicIntelligence(),
            scorer=DeterministicNewsScorer(),
            policy=load_news_policy(root),
            health=InMemoryHealthMonitor(),
            rate_limiter=InMemoryRateLimitManager(),
            circuit_breaker=InMemoryCircuitBreaker(),
            metrics=metrics,
            config_dir=root,
            entity_extractor=entities,
            event_detector=DefaultEventDetector(root),
            opportunity_detector=DefaultOpportunityDetector(root),
            trend_engine=trends,
            story_timeline=DefaultStoryTimelineBuilder(),
            taxonomy_assigner=DefaultTaxonomyAssigner(
                YamlTaxonomyLoader(root / "taxonomy" / "default.yaml")
            ),
            source_learning=learning,
        )
        return {
            "pipeline": pipeline,
            "source_registry": registry,
            "source_manager": manager,
            "scheduler": InProcessNewsScheduler(manager),
            "connectors": DefaultConnectorRegistry(),
            "policy": load_news_policy(root),
            "metrics": metrics,
            "normalizer": DefaultNormalizer(),
            "deduplicator": InMemoryDeduplicator(),
            "cluster": DefaultClusterEngine(),
            "topic": DefaultTopicIntelligence(),
            "scorer": DeterministicNewsScorer(),
            "health": InMemoryHealthMonitor(),
            "entities": entities,
            "events": DefaultEventDetector(root),
            "opportunities": DefaultOpportunityDetector(root),
            "trends": trends,
            "timelines": DefaultStoryTimelineBuilder(),
            "taxonomy": DefaultTaxonomyAssigner(
                YamlTaxonomyLoader(root / "taxonomy" / "default.yaml")
            ),
            "source_learning": learning,
        }
