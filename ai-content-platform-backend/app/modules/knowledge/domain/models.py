"""Knowledge Engine domain models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any


class KnowledgeType(str, Enum):
    ARTICLE = "article"
    EXAMPLE = "example"
    RULE = "rule"
    CLAIM = "claim"
    PREFERENCE = "preference"
    TEMPLATE = "template"
    BRAND = "brand"
    DOCUMENT = "document"
    DRAFT = "draft"
    APPROVED_POST = "approved_post"
    ORG_SETTING = "org_setting"
    USER_NOTE = "user_note"


class SearchMode(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    METADATA = "metadata"
    HYBRID = "hybrid"
    GRAPH = "graph"


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    id: str
    type: KnowledgeType
    organization_id: uuid.UUID | None
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_quality: float = 0.5
    confidence: float = 0.5
    reliability: float = 0.5
    freshness: float = 0.5
    authority: float = 0.5
    organization_relevance: float = 0.5
    created_at: datetime | None = None
    similarity: float | None = None
    rank_score: float | None = None
    source_name: str = ""

    def with_updates(self, **kwargs: Any) -> KnowledgeItem:
        return replace(self, **kwargs)


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    organization_id: uuid.UUID
    query_text: str
    correlation_id: str = ""
    types: tuple[KnowledgeType, ...] = ()
    search_mode: SearchMode = SearchMode.HYBRID
    top_k: int = 20
    token_budget: int = 4_000
    metadata_filters: dict[str, Any] = field(default_factory=dict)
    include_brand: bool = True
    include_examples: bool = True
    include_rules: bool = True
    include_claims: bool = True
    include_preferences: bool = True
    policy_id: str = "default"


@dataclass(frozen=True, slots=True)
class RankingWeights:
    similarity: float = 0.35
    keyword: float = 0.15
    reliability: float = 0.12
    freshness: float = 0.10
    authority: float = 0.08
    organization_relevance: float = 0.08
    confidence: float = 0.07
    feedback: float = 0.05


@dataclass(frozen=True, slots=True)
class KnowledgePolicy:
    policy_id: str = "default"
    source_priority: tuple[str, ...] = ()
    max_age_days: int = 365
    stale_below_score: float = 0.2
    require_org_match: bool = True
    allowed_languages: tuple[str, ...] = ("en",)
    deny_languages: tuple[str, ...] = ()
    allowed_types: tuple[str, ...] = ()
    min_confidence: float = 0.05
    min_reliability: float = 0.1
    drop_duplicate_claims: bool = True
    drop_content_duplicates: bool = True
    min_rank_score: float = 0.05
    ranking_weights: RankingWeights = field(default_factory=RankingWeights)


@dataclass(frozen=True, slots=True)
class PlannedQuery:
    search_type: SearchMode
    search_depth: int
    filters: dict[str, Any] = field(default_factory=dict)
    collections: tuple[str, ...] = ("knowledge",)
    policy_id: str = "default"
    query: KnowledgeQuery | None = None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    items: tuple[KnowledgeItem, ...]
    mode: SearchMode
    duration_ms: int = 0
    cache_hit: bool = False


@dataclass(frozen=True, slots=True)
class RankedKnowledge:
    items: tuple[KnowledgeItem, ...]
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class FilteredKnowledge:
    items: tuple[KnowledgeItem, ...]
    dropped_count: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class CompressedKnowledge:
    items: tuple[KnowledgeItem, ...]
    tokens_before: int = 0
    tokens_after: int = 0
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class CitationEntry:
    citation_id: str
    knowledge_id: str
    type: str
    title: str
    source: str
    rank_score: float | None = None
    snippet: str = ""


@dataclass(frozen=True, slots=True)
class CitationMap:
    entries: tuple[CitationEntry, ...] = ()

    @property
    def by_id(self) -> dict[str, CitationEntry]:
        return {e.citation_id: e for e in self.entries}

    def as_dicts(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "id": e.citation_id,
                "knowledge_id": e.knowledge_id,
                "type": e.type,
                "title": e.title,
                "source": e.source,
                "rank_score": e.rank_score,
                "snippet": e.snippet,
            }
            for e in self.entries
        )


@dataclass(frozen=True, slots=True)
class OptimizedContext:
    """Final assembled context for Prompt Builder / Writer (later milestones)."""

    text: str
    citations: tuple[dict[str, Any], ...] = ()
    citation_map: CitationMap = field(default_factory=CitationMap)
    knowledge_sources: tuple[str, ...] = ()
    items: tuple[KnowledgeItem, ...] = ()
    token_estimate: int = 0
    token_budget: int = 0
    sections: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: list[float]
    model_version: str
    dimensions: int
