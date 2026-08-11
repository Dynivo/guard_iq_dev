"""Knowledge Filter — policy-based filtering; never compresses tokens."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from app.modules.knowledge.domain.models import (
    FilteredKnowledge,
    KnowledgeItem,
    KnowledgePolicy,
    KnowledgeQuery,
    KnowledgeType,
    RankedKnowledge,
)


class DefaultKnowledgeFilter:
    async def filter(
        self,
        ranked: RankedKnowledge,
        query: KnowledgeQuery,
        policy: KnowledgePolicy,
    ) -> FilteredKnowledge:
        started = time.perf_counter()
        reasons: dict[str, int] = {}
        kept: list[KnowledgeItem] = []
        seen_content: set[str] = set()
        seen_claims: set[str] = set()
        now = datetime.now(timezone.utc)

        # Optional source priority ordering before filter pass
        items = list(ranked.items)
        if policy.source_priority:
            priority = {t: i for i, t in enumerate(policy.source_priority)}

            def _prio(item: KnowledgeItem) -> int:
                return priority.get(item.type.value, len(priority))

            items.sort(key=lambda i: (_prio(i), -(i.rank_score or 0.0)))

        for item in items:
            reason = self._drop_reason(item, query, policy, now)
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
                continue

            content_key = hashlib.sha256(
                f"{item.type.value}:{item.content.strip().lower()}".encode()
            ).hexdigest()[:16]

            if policy.drop_content_duplicates and content_key in seen_content:
                reasons["duplicate_content"] = reasons.get("duplicate_content", 0) + 1
                continue

            if item.type == KnowledgeType.CLAIM and policy.drop_duplicate_claims:
                claim_key = str(item.metadata.get("claim_id") or content_key)
                if claim_key in seen_claims:
                    reasons["duplicate_claim"] = reasons.get("duplicate_claim", 0) + 1
                    continue
                seen_claims.add(claim_key)

            seen_content.add(content_key)
            kept.append(item)

        duration_ms = int((time.perf_counter() - started) * 1000)
        dropped = len(ranked.items) - len(kept)
        return FilteredKnowledge(
            items=tuple(kept),
            dropped_count=dropped,
            drop_reasons=reasons,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _drop_reason(
        item: KnowledgeItem,
        query: KnowledgeQuery,
        policy: KnowledgePolicy,
        now: datetime,
    ) -> str | None:
        if not item.content.strip():
            return "empty_content"

        if policy.require_org_match:
            if (
                item.organization_id is not None
                and item.organization_id != query.organization_id
            ):
                return "organization_mismatch"

        if policy.allowed_types and item.type.value not in policy.allowed_types:
            return "category"

        lang = str(item.metadata.get("language") or "en").lower()
        if policy.deny_languages and lang in policy.deny_languages:
            return "language_denied"
        if policy.allowed_languages and lang not in policy.allowed_languages:
            return "language"

        if item.confidence < policy.min_confidence:
            return "confidence"
        reliability = item.reliability if item.reliability is not None else item.source_quality
        if reliability < policy.min_reliability:
            return "reliability"

        if item.rank_score is not None and item.rank_score < policy.min_rank_score:
            return "rank_score"

        if item.freshness < policy.stale_below_score:
            return "stale"

        if item.created_at is not None and policy.max_age_days > 0:
            created = item.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = (now - created).total_seconds() / 86400.0
            if age_days > policy.max_age_days:
                return "publication_age"

        return None
