"""Topic Intelligence — heuristic topic signals (no LLM)."""

from __future__ import annotations

from app.modules.ai_cache.application.namespaced import CacheNamespace, NamespacedAICache
from app.modules.content.domain.models import PlannerInput, PlannerPolicy, TopicSignals

_URGENT = ("breach", "ransomware", "urgent", "critical", "alert", "zero-day")
_TREND = ("2024", "2025", "2026", "rising", "trend", "emerging", "ai ")
_COMPLIANCE = ("compliance", "dspt", "gdpr", "hipaa", "audit")
_FRAMEWORKS = {
    "checklist": "checklist_5_7",
    "best practice": "best_practices_framework",
    "threat": "threat_impact_action",
    "compliance": "change_impact_checklist",
    "faq": "question_answer_series",
}


class DefaultTopicIntelligence:
    def __init__(self, cache: NamespacedAICache | None = None) -> None:
        self._cache = cache

    async def analyze(self, inp: PlannerInput, policy: PlannerPolicy) -> TopicSignals:
        topic = (inp.topic or "").lower()
        blob = f"{topic} {inp.industry} {(inp.context.text or '')[:800]}".lower()
        cache_key = f"{inp.organization_id}:{topic}:{inp.correlation_id}"
        if self._cache is not None:
            hit = await self._cache.get(CacheNamespace.TOPIC, cache_key)
            if hit:
                return TopicSignals(
                    novelty_score=float(hit.get("novelty_score", 0.5)),
                    urgency=float(hit.get("urgency", 0.5)),
                    trend_score=float(hit.get("trend_score", 0.5)),
                    popularity=float(hit.get("popularity", 0.5)),
                    business_impact=float(hit.get("business_impact", 0.5)),
                    seasonality=float(hit.get("seasonality", 0.5)),
                    category=str(hit.get("category") or "general"),
                    framework=str(hit.get("framework") or "hook_value_proof_cta"),
                )

        prev = set(" ".join(inp.previous_post_topics).lower().split())
        tokens = set(topic.split())
        overlap = len(tokens & prev) / max(1, len(tokens | prev)) if tokens else 0.0
        novelty = round(max(0.0, 1.0 - overlap), 3)

        urgency = 0.8 if any(u in blob for u in _URGENT) else 0.35
        if any(c in blob for c in _COMPLIANCE):
            urgency = max(urgency, 0.55)
        trend = 0.7 if any(t in blob for t in _TREND) else 0.4
        popularity = min(1.0, 0.4 + (inp.relevance_score or 0.5) * 0.5)
        business_impact = 0.75 if any(c in blob for c in _COMPLIANCE) else 0.5
        if urgency >= 0.7:
            business_impact = max(business_impact, 0.8)
        seasonality = 0.6 if "quarter" in blob or "year" in blob or "season" in blob else 0.45

        category = "general"
        if any(c in blob for c in _COMPLIANCE):
            category = "compliance"
        elif any(u in blob for u in _URGENT):
            category = "security"
        elif "healthcare" in blob or inp.industry.lower() in {"healthcare", "health"}:
            category = "healthcare"
        elif "checklist" in blob or "how to" in blob:
            category = "educational"

        framework = "hook_value_proof_cta"
        for needle, fw in _FRAMEWORKS.items():
            if needle in blob:
                framework = fw
                break

        signals = TopicSignals(
            novelty_score=novelty,
            urgency=round(urgency, 3),
            trend_score=round(trend, 3),
            popularity=round(popularity, 3),
            business_impact=round(business_impact, 3),
            seasonality=round(seasonality, 3),
            category=category,
            framework=framework,
        )
        if self._cache is not None:
            await self._cache.set(
                CacheNamespace.TOPIC,
                cache_key,
                {
                    "novelty_score": signals.novelty_score,
                    "urgency": signals.urgency,
                    "trend_score": signals.trend_score,
                    "popularity": signals.popularity,
                    "business_impact": signals.business_impact,
                    "seasonality": signals.seasonality,
                    "category": signals.category,
                    "framework": signals.framework,
                },
                ttl_seconds=600,
            )
        return signals
