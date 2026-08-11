"""News module ports — M8 intelligence pipeline contracts."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.modules.news.domain.models import (
    ArticleCluster,
    CanonicalArticle,
    DetectedEvent,
    ExtractedEntities,
    NewsPolicy,
    NewsScore,
    NormalizedArticle,
    OpportunitySignals,
    PipelineResult,
    SourceDefinition,
    SourceFeedbackEvent,
    SourceHealth,
    StoryTimeline,
    TaxonomyPath,
    TopicSignals,
    TrendMetrics,
)

# Re-export for connectors that import from ports
__all__ = [
    "NormalizedArticle",
    "NewsConnector",
    "ArticleRepository",
    "Deduplicator",
    "Normalizer",
    "ClusterEngine",
    "TopicIntelligence",
    "NewsScorer",
    "SourceManager",
    "SourceRegistry",
    "ConnectorRegistry",
    "NewsScheduler",
    "NewsPipeline",
    "HealthMonitor",
    "RateLimitManager",
    "CircuitBreaker",
    "SourceReputationEngine",
    "FeedValidator",
    "ContentValidator",
    "LanguageDetector",
    "EntityExtractor",
    "EventDetector",
    "OpportunityDetector",
    "TrendEngine",
    "StoryTimelineBuilder",
    "TaxonomyAssigner",
    "SourceLearningStore",
]


class NewsConnector(Protocol):
    connector_type: str

    async def fetch(self, config: dict) -> list[NormalizedArticle]: ...

    async def validate_config(self, config: dict) -> tuple[bool, str]: ...

    async def health(self) -> SourceHealth: ...


class ArticleRepository(Protocol):
    async def save(
        self, article: NormalizedArticle, org_id: uuid.UUID, source_id: uuid.UUID
    ) -> uuid.UUID: ...

    async def exists_by_url(self, org_id: uuid.UUID, url: str) -> bool: ...


class Deduplicator(Protocol):
    async def is_duplicate(
        self, org_id: uuid.UUID, url: str, content_hash: str | None = None
    ) -> bool: ...

    async def mark_seen(self, org_id: uuid.UUID, url: str) -> None: ...

    def is_near_duplicate(
        self, left: CanonicalArticle, right: CanonicalArticle, *, threshold: float
    ) -> bool: ...


class Normalizer(Protocol):
    def normalize(
        self,
        raw: NormalizedArticle | dict[str, Any],
        *,
        source: SourceDefinition | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> CanonicalArticle: ...


class ClusterEngine(Protocol):
    def cluster(
        self, articles: list[CanonicalArticle], *, policy: NewsPolicy
    ) -> list[ArticleCluster]: ...


class TopicIntelligence(Protocol):
    def analyze(self, article: CanonicalArticle, *, policy: NewsPolicy) -> TopicSignals: ...


class NewsScorer(Protocol):
    def score(
        self,
        article: CanonicalArticle,
        *,
        topic: TopicSignals,
        source: SourceDefinition | None,
        policy: NewsPolicy,
    ) -> NewsScore: ...


class SourceManager(Protocol):
    def list_enabled(self, organization_id: str | None = None) -> list[SourceDefinition]: ...

    def get(self, source_id: str) -> SourceDefinition | None: ...


class SourceRegistry(Protocol):
    def list_all(self) -> list[SourceDefinition]: ...

    def get(self, source_id: str) -> SourceDefinition | None: ...

    def register(self, definition: SourceDefinition) -> None: ...


class ConnectorRegistry(Protocol):
    def get(self, connector_type: str) -> Any: ...

    def list_types(self) -> list[str]: ...

    def register(self, connector_type: str, factory: Any) -> None: ...


class NewsScheduler(Protocol):
    def due_sources(
        self, *, trigger: str = "periodic"
    ) -> list[SourceDefinition]: ...

    async def enqueue(
        self, source: SourceDefinition, *, priority: int = 0
    ) -> str: ...


class NewsPipeline(Protocol):
    async def run(
        self,
        source: SourceDefinition,
        *,
        organization_id: uuid.UUID | None = None,
        items: list[NormalizedArticle] | None = None,
    ) -> PipelineResult: ...


class HealthMonitor(Protocol):
    def record_success(self, source_id: str, latency_ms: float) -> None: ...

    def record_failure(self, source_id: str, error: str) -> None: ...

    def get(self, source_id: str) -> SourceHealth: ...


class RateLimitManager(Protocol):
    def allow(self, key: str) -> bool: ...

    def record(self, key: str) -> None: ...


class CircuitBreaker(Protocol):
    def allow(self, key: str) -> bool: ...

    def record_success(self, key: str) -> None: ...

    def record_failure(self, key: str) -> None: ...


class SourceReputationEngine(Protocol):
    def reputation(self, source: SourceDefinition) -> dict[str, float]: ...


class FeedValidator(Protocol):
    def validate_items(self, items: list[NormalizedArticle]) -> tuple[list[NormalizedArticle], list[str]]: ...


class ContentValidator(Protocol):
    def validate(self, article: CanonicalArticle) -> tuple[bool, str]: ...


class LanguageDetector(Protocol):
    def detect(self, text: str) -> str: ...


class EntityExtractor(Protocol):
    def extract(
        self, article: CanonicalArticle, *, topic: TopicSignals | None = None
    ) -> ExtractedEntities: ...


class EventDetector(Protocol):
    def detect(
        self, article: CanonicalArticle, *, topic: TopicSignals | None = None
    ) -> list[DetectedEvent]: ...


class OpportunityDetector(Protocol):
    def detect(
        self,
        article: CanonicalArticle,
        *,
        topic: TopicSignals,
        score: NewsScore,
        cluster: ArticleCluster | None = None,
        events: list[str] | None = None,
    ) -> OpportunitySignals: ...


class TrendEngine(Protocol):
    def observe_batch(
        self, articles: list[CanonicalArticle], topics: list[TopicSignals]
    ) -> list[TrendMetrics]: ...

    def get(self, topic_key: str) -> TrendMetrics | None: ...


class StoryTimelineBuilder(Protocol):
    def build(
        self,
        clusters: list[ArticleCluster],
        articles: list[CanonicalArticle],
        *,
        events_by_url: dict[str, list[str]] | None = None,
    ) -> list[StoryTimeline]: ...


class TaxonomyAssigner(Protocol):
    def assign(
        self,
        article: CanonicalArticle,
        *,
        topic: TopicSignals,
        entities: ExtractedEntities | None = None,
    ) -> TaxonomyPath: ...


class SourceLearningStore(Protocol):
    def record(self, event: SourceFeedbackEvent) -> None: ...

    def list_events(self, source_id: str) -> list[SourceFeedbackEvent]: ...

    def upsert_source(self, source: SourceDefinition) -> None: ...

    def get_source(self, source_id: str) -> SourceDefinition | None: ...
