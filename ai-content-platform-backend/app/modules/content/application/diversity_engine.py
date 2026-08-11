"""Content Diversity Engine — reduce repetitive plans."""

from __future__ import annotations

from collections import Counter

from app.modules.content.domain.models import (
    Audience,
    CTA,
    ContentType,
    DiversityRecommendation,
    PlannerInput,
    PlannerPolicy,
    RecentContentHistory,
)


class DefaultContentDiversityEngine:
    def recommend(
        self,
        inp: PlannerInput,
        policy: PlannerPolicy,
        recent: RecentContentHistory,
    ) -> DiversityRecommendation:
        types = list(recent.content_types) + list(inp.previous_content_types)
        ctas = list(recent.ctas) + list(inp.previous_ctas)
        audiences = list(recent.audiences) + list(inp.previous_audiences)
        topics = list(recent.topics) + list(inp.previous_post_topics)

        reasons: list[str] = []
        alt_type = None
        alt_cta = None
        alt_audience = None

        type_share = _max_share(types)
        cta_share = _max_share(ctas)
        aud_share = _max_share(audiences)

        if type_share >= policy.diversity_max_type_share and types:
            dominant = Counter(types).most_common(1)[0][0]
            alt_type = _alternate_type(dominant, policy)
            reasons.append(f"type_concentration={type_share:.2f} dominant={dominant}")

        if cta_share >= policy.diversity_max_cta_share and ctas:
            dominant = Counter(ctas).most_common(1)[0][0]
            alt_cta = _alternate_cta(dominant, policy)
            reasons.append(f"cta_concentration={cta_share:.2f}")

        if aud_share >= policy.diversity_max_audience_share and audiences:
            dominant = Counter(audiences).most_common(1)[0][0]
            alt_audience = _alternate_audience(dominant, policy)
            reasons.append(f"audience_concentration={aud_share:.2f}")

        topic_rep = 0.0
        topic = (inp.topic or "").lower()
        if topic and topics:
            t_tokens = set(topic.split())
            best = 0.0
            for prev in topics:
                p = set(prev.lower().split())
                if not p:
                    continue
                best = max(best, len(t_tokens & p) / max(1, len(t_tokens | p)))
            topic_rep = best
            if topic_rep >= 0.6:
                reasons.append(f"topic_overlap={topic_rep:.2f}")

        repetition = round(
            max(type_share, cta_share, aud_share, topic_rep),
            3,
        )
        return DiversityRecommendation(
            repetition_score=repetition,
            recommend_alternate_type=alt_type,
            recommend_alternate_cta=alt_cta,
            recommend_alternate_audience=alt_audience,
            reasons=tuple(reasons),
        )


def _max_share(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    return counts.most_common(1)[0][1] / len(values)


def _alternate_type(dominant: str, policy: PlannerPolicy) -> str:
    candidates = list(policy.preferred_content_types) or [
        ContentType.EDUCATIONAL.value,
        ContentType.THOUGHT_LEADERSHIP.value,
        ContentType.CHECKLIST.value,
        ContentType.COMPLIANCE_UPDATE.value,
    ]
    for c in candidates:
        if c != dominant:
            return c
    return ContentType.OPINION.value


def _alternate_cta(dominant: str, policy: PlannerPolicy) -> str:
    for c in policy.allowed_ctas or [x.value for x in CTA]:
        if c != dominant:
            return c
    return CTA.FOLLOW.value


def _alternate_audience(dominant: str, policy: PlannerPolicy) -> str:
    for a in policy.preferred_audiences or [x.value for x in Audience]:
        if a != dominant:
            return a
    return Audience.IT_MANAGERS.value
