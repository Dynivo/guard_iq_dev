"""News Intelligence domain models (M8)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ArticleLifecycleStatus(str, Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    DUPLICATE = "duplicate"
    CLUSTERED = "clustered"
    SCORED = "scored"
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    USED = "used"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ScheduleTrigger(str, Enum):
    CRON = "cron"
    MANUAL = "manual"
    WEBHOOK = "webhook"
    PERIODIC = "periodic"
    PRIORITY = "priority"


@dataclass(frozen=True, slots=True)
class CanonicalArticle:
    """Single normalized schema for all connectors."""

    title: str
    url: str
    canonical_url: str = ""
    summary: str = ""
    body_text: str = ""
    author: str = ""
    source: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    language: str = "en"
    published_at: datetime | None = None
    updated_at: datetime | None = None
    images: tuple[str, ...] = ()
    organization_id: uuid.UUID | None = None
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "canonical_url": self.canonical_url or self.url,
            "summary": self.summary,
            "body_text": self.body_text,
            "author": self.author,
            "source": self.source,
            "category": self.category,
            "tags": list(self.tags),
            "language": self.language,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "images": list(self.images),
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "content_hash": self.content_hash,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class TopicSignals:
    category: str = ""
    industry: str = ""
    threat: str = ""
    technology: str = ""
    country: str = ""
    company: str = ""
    framework: str = ""
    urgency: float = 0.0
    trend: float = 0.0
    business_impact: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "industry": self.industry,
            "threat": self.threat,
            "technology": self.technology,
            "country": self.country,
            "company": self.company,
            "framework": self.framework,
            "urgency": self.urgency,
            "trend": self.trend,
            "business_impact": self.business_impact,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class NewsScore:
    relevance: float = 0.0
    importance: float = 0.0
    authority: float = 0.0
    novelty: float = 0.0
    trend: float = 0.0
    business_impact: float = 0.0
    organization_relevance: float = 0.0
    freshness: float = 0.0
    confidence: float = 0.0
    composite: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "relevance": self.relevance,
            "importance": self.importance,
            "authority": self.authority,
            "novelty": self.novelty,
            "trend": self.trend,
            "business_impact": self.business_impact,
            "organization_relevance": self.organization_relevance,
            "freshness": self.freshness,
            "confidence": self.confidence,
            "composite": self.composite,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ArticleCluster:
    cluster_id: str
    label: str
    article_urls: tuple[str, ...] = ()
    cohesion: float = 0.0
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    source_id: str
    name: str
    connector_type: str
    config: dict[str, Any] = field(default_factory=dict)
    schedule_cron: str = ""
    enabled: bool = True
    organization_id: str = ""
    authority: float = 0.5
    reliability: float = 0.5
    trust: float = 0.5


@dataclass(frozen=True, slots=True)
class SourceHealth:
    source_id: str
    healthy: bool
    circuit_state: CircuitState = CircuitState.CLOSED
    failure_rate: float = 0.0
    last_error: str = ""
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NewsPolicy:
    policy_id: str = "default"
    title_similarity_threshold: float = 0.85
    cluster_similarity_threshold: float = 0.55
    cluster_time_window_hours: int = 72
    max_cluster_size: int = 20
    min_authority: float = 0.0
    score_weights: dict[str, float] = field(
        default_factory=lambda: {
            "relevance": 0.20,
            "importance": 0.12,
            "authority": 0.12,
            "novelty": 0.10,
            "trend": 0.10,
            "business_impact": 0.12,
            "organization_relevance": 0.14,
            "freshness": 0.10,
        }
    )
    relevant_composite_threshold: float = 0.45


@dataclass(frozen=True, slots=True)
class PipelineResult:
    source_id: str
    fetched: int = 0
    normalized: int = 0
    duplicates: int = 0
    clustered: int = 0
    scored: int = 0
    stored: int = 0
    articles: tuple[CanonicalArticle, ...] = ()
    clusters: tuple[ArticleCluster, ...] = ()
    scores: tuple[NewsScore, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "fetched": self.fetched,
            "normalized": self.normalized,
            "duplicates": self.duplicates,
            "clustered": self.clustered,
            "scored": self.scored,
            "stored": self.stored,
            "articles": [a.to_dict() for a in self.articles],
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "label": c.label,
                    "article_urls": list(c.article_urls),
                    "cohesion": c.cohesion,
                }
                for c in self.clusters
            ],
            "scores": [s.to_dict() for s in self.scores],
            "metrics": dict(self.metrics),
            "errors": list(self.errors),
        }


class OpportunityType(str, Enum):
    EDUCATIONAL = "educational"
    THOUGHT_LEADERSHIP = "thought_leadership"
    CHECKLIST = "checklist"
    BEST_PRACTICES = "best_practices"
    WEEKLY_ROUNDUP = "weekly_roundup_candidate"
    INDUSTRY_ALERT = "industry_alert"
    SECURITY_ADVISORY = "security_advisory"
    COMPLIANCE_UPDATE = "compliance_update"
    MYTH_VS_FACT = "myth_vs_fact"
    FAQ = "faq"
    COMPARISON = "comparison"
    MULTI_ARTICLE_MERGE = "multi_article_merge"


class NewsEventType(str, Enum):
    BREACH = "breach"
    ACQUISITION = "acquisition"
    PRODUCT_LAUNCH = "product_launch"
    PATCH_RELEASE = "patch_release"
    VULNERABILITY = "vulnerability"
    FUNDING = "funding"
    REGULATION = "regulation"
    COMPLIANCE = "compliance"
    INCIDENT = "incident"


class SourceFeedbackKind(str, Enum):
    APPROVAL = "approval"
    REJECTION = "rejection"
    USER_EDIT = "user_edit"
    ENGAGEMENT = "engagement"


@dataclass(frozen=True, slots=True)
class OpportunitySignals:
    types: tuple[str, ...] = ()
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "types": list(self.types),
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ExtractedEntities:
    companies: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    cves: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    regulations: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "companies": list(self.companies),
            "products": list(self.products),
            "technologies": list(self.technologies),
            "cves": list(self.cves),
            "countries": list(self.countries),
            "industries": list(self.industries),
            "regulations": list(self.regulations),
            "frameworks": list(self.frameworks),
        }

    def flat_records(self) -> list[tuple[str, str]]:
        mapping = [
            ("company", self.companies),
            ("product", self.products),
            ("technology", self.technologies),
            ("cve", self.cves),
            ("country", self.countries),
            ("industry", self.industries),
            ("regulation", self.regulations),
            ("framework", self.frameworks),
        ]
        records: list[tuple[str, str]] = []
        for etype, values in mapping:
            for v in values:
                records.append((etype, v))
        return records


@dataclass(frozen=True, slots=True)
class DetectedEvent:
    event_type: str
    confidence: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class TrendMetrics:
    topic_key: str
    growth: float = 0.0
    momentum: float = 0.0
    velocity: float = 0.0
    popularity: float = 0.0
    predicted_trend: float = 0.0
    article_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_key": self.topic_key,
            "growth": self.growth,
            "momentum": self.momentum,
            "velocity": self.velocity,
            "popularity": self.popularity,
            "predicted_trend": self.predicted_trend,
            "article_count": self.article_count,
        }


@dataclass(frozen=True, slots=True)
class StoryTimeline:
    story_id: str
    label: str
    article_urls: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    started_at: datetime | None = None
    updated_at: datetime | None = None
    cohesion: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_id": self.story_id,
            "label": self.label,
            "article_urls": list(self.article_urls),
            "events": list(self.events),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "cohesion": self.cohesion,
        }


@dataclass(frozen=True, slots=True)
class TaxonomyPath:
    industry: str = ""
    topic: str = ""
    subtopic: str = ""
    framework: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "industry": self.industry,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "framework": self.framework,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class SourceFeedbackEvent:
    source_id: str
    kind: SourceFeedbackKind
    weight: float = 1.0
    article_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Backward-compatible alias used by existing connectors
@dataclass
class NormalizedArticle:
    """Legacy connector shape — Normalizer lifts this to CanonicalArticle."""

    title: str
    url: str
    summary: str | None = None
    body_text: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    raw_payload: dict | None = None
