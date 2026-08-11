"""Deterministic Strategy Engine — consumes topic/diversity/priority signals."""

from __future__ import annotations

from app.modules.content.domain.models import (
    ContentFormat,
    ContentType,
    PlannerInput,
    PlannerPolicy,
    StrategyAction,
    StrategyDecision,
)

_SECURITY_HINTS = ("security", "breach", "ransomware", "phishing", "mfa", "zero trust")
_COMPLIANCE_HINTS = ("compliance", "dspt", "gdpr", "hipaa", "audit", "regulation")
_CHECKLIST_HINTS = ("checklist", "steps", "how to", "guide", "playbook")
_NEWS_HINTS = ("announces", "launches", "update", "breaking", "report")


class DefaultStrategyEngine:
    async def evaluate(
        self, inp: PlannerInput, policy: PlannerPolicy
    ) -> StrategyDecision:
        reasons: list[str] = []
        alternatives: list[str] = []
        topic = (inp.topic or _topic_from_context(inp) or "").lower()
        text_blob = _context_blob(inp).lower()
        topic_signals = inp.topic_signals
        diversity = inp.diversity
        priority = inp.priority

        relevance = (
            inp.relevance_score
            if inp.relevance_score is not None
            else _estimate_relevance(inp)
        )
        if inp.relevance_score is None and topic_signals:
            relevance = max(
                relevance,
                topic_signals.popularity * 0.5 + topic_signals.business_impact * 0.5,
            )

        duplicate_score = _duplicate_score(topic, inp.previous_post_topics)
        if diversity:
            duplicate_score = max(duplicate_score, diversity.repetition_score)

        if relevance < policy.min_relevance:
            return StrategyDecision(
                action=StrategyAction.IGNORE,
                recommended_type=ContentType.INDUSTRY_NEWS,
                format=ContentFormat.SINGLE,
                confidence=round(max(0.0, relevance), 3),
                duplicate_score=duplicate_score,
                reasons=(
                    f"relevance {relevance:.2f} below min {policy.min_relevance}",
                ),
                alternatives=("wait_for_higher_relevance", "merge_into_roundup"),
                metrics={"relevance": relevance, "duplicate_score": duplicate_score},
            )

        if duplicate_score >= policy.max_duplicate_score:
            return StrategyDecision(
                action=StrategyAction.IGNORE,
                recommended_type=ContentType.INDUSTRY_NEWS,
                format=ContentFormat.SINGLE,
                confidence=round(1.0 - duplicate_score, 3),
                duplicate_score=duplicate_score,
                reasons=(
                    f"duplicate_score {duplicate_score:.2f} >= max {policy.max_duplicate_score}",
                ),
                alternatives=("reframe_angle", "combine_as_weekly_roundup"),
                metrics={"relevance": relevance, "duplicate_score": duplicate_score},
            )

        content_type = _recommend_type(topic, text_blob, inp, policy)
        reasons.append(f"type={content_type.value}")
        alternatives.append(ContentType.THOUGHT_LEADERSHIP.value)
        alternatives.append(ContentType.EDUCATIONAL.value)

        if diversity and diversity.recommend_alternate_type:
            alternatives.append(diversity.recommend_alternate_type)
            if diversity.repetition_score >= policy.diversity_max_type_share:
                content_type = ContentType(diversity.recommend_alternate_type)
                reasons.append("diversity_type_override")
                reasons.extend(diversity.reasons)

        if priority and priority.preferred_type and content_type == ContentType.EDUCATIONAL:
            try:
                content_type = ContentType(priority.preferred_type)
                reasons.append("business_priority_type")
            except ValueError:
                pass

        if topic_signals and topic_signals.urgency >= 0.75:
            content_type = ContentType.SECURITY_ALERT
            reasons.append("topic_urgency_security")

        fmt = ContentFormat.CAROUSEL
        if content_type.value in policy.force_carousel_types:
            fmt = ContentFormat.CAROUSEL
            reasons.append("force_carousel_by_policy")
        elif content_type in {
            ContentType.SECURITY_ALERT,
            ContentType.OPINION,
            ContentType.INDUSTRY_NEWS,
            ContentType.SINGLE_POST,
        }:
            fmt = ContentFormat.SINGLE
            reasons.append("single_format_for_type")
            alternatives.append("carousel_deep_dive")
        else:
            fmt = ContentFormat.CAROUSEL
            reasons.append("carousel_default_for_type")

        if content_type == ContentType.CAROUSEL:
            content_type = ContentType.EDUCATIONAL
            fmt = ContentFormat.CAROUSEL

        confidence = _confidence(
            relevance, duplicate_score, content_type, policy, topic_signals, priority
        )
        if confidence < policy.min_confidence:
            return StrategyDecision(
                action=StrategyAction.IGNORE,
                recommended_type=content_type,
                format=fmt,
                confidence=confidence,
                duplicate_score=duplicate_score,
                reasons=tuple(reasons + [f"confidence {confidence:.2f} below min"]),
                alternatives=tuple(dict.fromkeys(alternatives)),
                metrics={"relevance": relevance, "duplicate_score": duplicate_score},
            )

        should_merge = ContentType.WEEKLY_ROUNDUP == content_type
        if should_merge:
            reasons.append("weekly_roundup_merge_signal")

        if inp.calendar and not inp.calendar.frequency_ok:
            reasons.append("calendar_frequency_caution")

        return StrategyDecision(
            action=StrategyAction.CREATE,
            recommended_type=content_type,
            format=fmt,
            confidence=confidence,
            duplicate_score=duplicate_score,
            reasons=tuple(reasons),
            should_merge_articles=should_merge,
            alternatives=tuple(dict.fromkeys(alternatives)),
            metrics={
                "relevance": relevance,
                "duplicate_score": duplicate_score,
                "content_type": content_type.value,
                "format": fmt.value,
                "topic_category": topic_signals.category if topic_signals else "",
                "priority_score": priority.score if priority else 0.0,
            },
        )


def _topic_from_context(inp: PlannerInput) -> str:
    if inp.context.sections.get("knowledge"):
        line = inp.context.sections["knowledge"].split("\n", 1)[0]
        return line[:200]
    return inp.context.text[:120] if inp.context.text else ""


def _context_blob(inp: PlannerInput) -> str:
    parts = [
        inp.topic,
        inp.industry,
        inp.context.text[:2000] if inp.context.text else "",
        " ".join(inp.context.sections.values())[:2000],
    ]
    meta = inp.article_metadata or {}
    parts.append(str(meta.get("title") or ""))
    parts.append(str(meta.get("summary") or ""))
    return " ".join(parts)


def _estimate_relevance(inp: PlannerInput) -> float:
    if inp.context.items:
        scores = [i.rank_score or i.similarity or 0.5 for i in inp.context.items]
        return min(1.0, sum(scores) / max(1, len(scores)))
    if inp.context.token_estimate > 0:
        return 0.55
    return 0.35


def _duplicate_score(topic: str, previous: tuple[str, ...]) -> float:
    if not topic or not previous:
        return 0.0
    t_tokens = set(topic.lower().split())
    best = 0.0
    for prev in previous:
        p_tokens = set(prev.lower().split())
        if not p_tokens:
            continue
        overlap = len(t_tokens & p_tokens) / max(1, len(t_tokens | p_tokens))
        best = max(best, overlap)
    return round(best, 3)


def _recommend_type(
    topic: str, blob: str, inp: PlannerInput, policy: PlannerPolicy
) -> ContentType:
    preferred = policy.preferred_content_types
    hay = f"{topic} {blob} {inp.industry}".lower()

    if any(h in hay for h in _CHECKLIST_HINTS):
        return ContentType.CHECKLIST
    if any(h in hay for h in _SECURITY_HINTS):
        return ContentType.SECURITY_ALERT
    if any(h in hay for h in _COMPLIANCE_HINTS):
        return ContentType.COMPLIANCE_UPDATE
    if "roundup" in hay or "this week" in hay:
        return ContentType.WEEKLY_ROUNDUP
    if "case study" in hay or "customer" in hay:
        return ContentType.CASE_STUDY
    if "faq" in hay or "questions" in hay:
        return ContentType.FAQ
    if any(h in hay for h in _NEWS_HINTS):
        return ContentType.INDUSTRY_NEWS
    if "thought" in hay or "opinion" in hay or "leadership" in hay:
        return ContentType.THOUGHT_LEADERSHIP
    if preferred:
        try:
            return ContentType(preferred[0])
        except ValueError:
            pass
    return ContentType.EDUCATIONAL


def _confidence(
    relevance: float,
    duplicate_score: float,
    content_type: ContentType,
    policy: PlannerPolicy,
    topic_signals,
    priority,
) -> float:
    base = 0.4 * relevance + 0.3 * (1.0 - duplicate_score) + 0.15
    if policy.preferred_content_types and content_type.value in policy.preferred_content_types:
        base += 0.05
    if topic_signals:
        base += 0.05 * topic_signals.novelty_score + 0.05 * topic_signals.business_impact
    if priority:
        base += 0.05 * priority.score
    return round(min(1.0, max(0.0, base)), 3)
