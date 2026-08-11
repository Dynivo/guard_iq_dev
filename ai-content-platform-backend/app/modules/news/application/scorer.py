"""News Scorer — multi-signal composite from policy weights (no product keyword hardcoding)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.modules.news.domain.models import (
    CanonicalArticle,
    NewsPolicy,
    NewsScore,
    SourceDefinition,
    TopicSignals,
)


class DeterministicNewsScorer:
    """Offline/CI scorer using TopicSignals + source reputation + freshness.

    Optional brand_terms / exclude_terms raise or lower organization_relevance
    from BrandNewsPolicy (Brand Memory DNA).
    """

    def score(
        self,
        article: CanonicalArticle,
        *,
        topic: TopicSignals,
        source: SourceDefinition | None,
        policy: NewsPolicy,
        brand_terms: Sequence[str] | None = None,
        exclude_terms: Sequence[str] | None = None,
    ) -> NewsScore:
        authority = (source.authority if source else 0.5) * (source.trust if source else 0.5) ** 0.5
        authority = max(0.0, min(1.0, authority))

        freshness = _freshness(article.published_at)
        relevance = min(
            1.0,
            0.35 * topic.confidence
            + 0.25 * topic.business_impact
            + 0.20 * (1.0 if topic.framework or topic.industry else 0.3)
            + 0.20 * topic.urgency,
        )
        importance = min(1.0, 0.5 * topic.urgency + 0.5 * topic.business_impact)
        novelty = 0.7 if not article.metadata.get("near_duplicate") else 0.2
        trend = topic.trend
        business_impact = topic.business_impact
        org_rel = min(
            1.0,
            0.4 * topic.confidence
            + 0.3 * (1.0 if topic.industry else 0.2)
            + 0.3 * (1.0 if topic.framework else 0.2),
        )
        blob = f"{article.title} {article.summary} {article.body_text}".lower()
        hits = 0
        for term in brand_terms or ():
            t = str(term).strip().lower()
            if t and t in blob:
                hits += 1
        excl = 0
        for term in exclude_terms or ():
            t = str(term).strip().lower()
            if t and t in blob:
                excl += 1
        org_rel = min(1.0, max(0.0, org_rel + min(0.45, hits * 0.07) - min(0.5, excl * 0.12)))
        if hits:
            relevance = min(1.0, relevance + min(0.2, hits * 0.03))
        confidence = min(1.0, topic.confidence + (0.05 if hits else 0.0))

        weights = policy.score_weights
        composite = (
            weights.get("relevance", 0.2) * relevance
            + weights.get("importance", 0.12) * importance
            + weights.get("authority", 0.12) * authority
            + weights.get("novelty", 0.10) * novelty
            + weights.get("trend", 0.10) * trend
            + weights.get("business_impact", 0.12) * business_impact
            + weights.get("organization_relevance", 0.14) * org_rel
            + weights.get("freshness", 0.10) * freshness
        )

        return NewsScore(
            relevance=relevance,
            importance=importance,
            authority=authority,
            novelty=novelty,
            trend=trend,
            business_impact=business_impact,
            organization_relevance=org_rel,
            freshness=freshness,
            confidence=confidence,
            composite=round(composite, 4),
            reason=(
                f"topic={topic.category}; industry={topic.industry}; "
                f"framework={topic.framework}; threat={topic.threat}; "
                f"brand_hits={hits}; brand_excl={excl}"
            ),
        )


def _freshness(published: datetime | None) -> float:
    if published is None:
        return 0.4
    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - published).total_seconds() / 3600.0)
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.8
    if age_hours <= 168:
        return 0.55
    if age_hours <= 720:
        return 0.35
    return 0.15
