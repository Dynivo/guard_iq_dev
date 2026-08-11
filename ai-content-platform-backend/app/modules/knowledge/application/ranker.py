"""Heuristic ranker — scores with reliability/freshness/authority signals."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from app.modules.knowledge.domain.models import (
    KnowledgeItem,
    KnowledgePolicy,
    KnowledgeQuery,
    RankedKnowledge,
    RankingWeights,
)


def _compute_freshness(
    created_at: datetime | None, *, now: datetime, max_age_days: int
) -> float:
    if created_at is None:
        return 0.5
    created = created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    if max_age_days <= 0:
        return 1.0
    return max(0.0, 1.0 - min(age_days, float(max_age_days)) / float(max_age_days))


class HeuristicRanker:
    def __init__(self, policy: KnowledgePolicy | None = None) -> None:
        self._policy = policy or KnowledgePolicy()

    async def rank(
        self, items: tuple[KnowledgeItem, ...], query: KnowledgeQuery
    ) -> RankedKnowledge:
        started = time.perf_counter()
        now = datetime.now(timezone.utc)
        weights: RankingWeights = self._policy.ranking_weights
        ranked: list[KnowledgeItem] = []
        q = query.query_text.lower()

        for item in items:
            similarity = item.similarity if item.similarity is not None else 0.0
            kw = 0.0
            if q and (q in item.title.lower() or q in item.content.lower()):
                kw = 1.0

            freshness = item.freshness
            if item.created_at is not None:
                freshness = _compute_freshness(
                    item.created_at,
                    now=now,
                    max_age_days=self._policy.max_age_days,
                )

            reliability = item.reliability
            if item.reliability == 0.5 and item.source_quality != 0.5:
                reliability = item.source_quality

            authority = item.authority
            org_rel = item.organization_relevance
            if item.organization_id == query.organization_id:
                org_rel = max(org_rel, 1.0)
            elif item.organization_id is None:
                org_rel = max(org_rel, 0.7)

            feedback = min(float(item.metadata.get("approval_count", 0)) * 0.2, 1.0)

            score = (
                similarity * weights.similarity
                + kw * weights.keyword
                + reliability * weights.reliability
                + freshness * weights.freshness
                + authority * weights.authority
                + org_rel * weights.organization_relevance
                + item.confidence * weights.confidence
                + feedback * weights.feedback
            )
            ranked.append(
                item.with_updates(
                    reliability=reliability,
                    freshness=freshness,
                    authority=authority,
                    organization_relevance=org_rel,
                    rank_score=round(score, 6),
                )
            )

        ranked.sort(key=lambda i: i.rank_score or 0.0, reverse=True)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return RankedKnowledge(items=tuple(ranked), duration_ms=duration_ms)
