"""Default Content Planner — assembles candidate plans; never validates; never calls providers."""

from __future__ import annotations

import time
import uuid
from dataclasses import replace

from app.core.logging import get_logger
from app.modules.ai_cache.application.namespaced import (
    CacheNamespace,
    NamespacedAICache,
)
from app.modules.content.application.audience_engine import DefaultAudienceEngine
from app.modules.content.application.business_priority import DefaultBusinessPriorityEngine
from app.modules.content.application.calendar_awareness import FortnightCalendarAwareness
from app.modules.content.application.diversity_engine import DefaultContentDiversityEngine
from app.modules.content.application.strategy import DefaultStrategyEngine
from app.modules.content.application.topic_intelligence import DefaultTopicIntelligence
from app.modules.content.domain.models import (
    CTA,
    AudienceProfile,
    CalendarContext,
    CarouselStructure,
    ContentFormat,
    ContentPlan,
    ContentType,
    DiversityRecommendation,
    Goal,
    PlanStatus,
    PlannerExplanation,
    PlannerInput,
    PlannerPolicy,
    PrioritySignals,
    RecentContentHistory,
    SlideOutline,
    StrategyAction,
    StrategyDecision,
    Tone,
    TopicSignals,
)
from app.modules.content.domain.ports import (
    AudienceEngine,
    BusinessPriorityEngine,
    CalendarAwareness,
    ContentDiversityEngine,
    ContentPlanRepository,
    StrategyEngine,
    TopicIntelligence,
)
from app.modules.content.infrastructure.plan_repository import InMemoryContentPlanRepository

logger = get_logger(__name__)


class DefaultContentPlanner:
    def __init__(
        self,
        *,
        strategy: StrategyEngine | None = None,
        repository: ContentPlanRepository | None = None,
        policy: PlannerPolicy | None = None,
        cache: NamespacedAICache | None = None,
        topic_intelligence: TopicIntelligence | None = None,
        audience_engine: AudienceEngine | None = None,
        diversity_engine: ContentDiversityEngine | None = None,
        calendar: CalendarAwareness | None = None,
        business_priority: BusinessPriorityEngine | None = None,
    ) -> None:
        self._strategy = strategy or DefaultStrategyEngine()
        self._repo = repository or InMemoryContentPlanRepository()
        self._policy = policy or PlannerPolicy()
        self._cache = cache
        self._topic = topic_intelligence or DefaultTopicIntelligence(cache)
        self._audience = audience_engine or DefaultAudienceEngine()
        self._diversity = diversity_engine or DefaultContentDiversityEngine()
        self._calendar = calendar or FortnightCalendarAwareness()
        self._priority = business_priority or DefaultBusinessPriorityEngine()

    async def _enrich(self, inp: PlannerInput) -> PlannerInput:
        topic_signals = inp.topic_signals or await self._topic.analyze(inp, self._policy)
        audience = inp.audience_profile or self._audience.resolve(inp, self._policy)
        recent = RecentContentHistory(
            topics=inp.previous_post_topics,
            content_types=inp.previous_content_types,
            ctas=inp.previous_ctas,
            audiences=inp.previous_audiences,
        )
        diversity = inp.diversity or self._diversity.recommend(inp, self._policy, recent)
        priority = inp.priority or self._priority.score(inp, self._policy)
        calendar = inp.calendar or self._calendar.snapshot(inp.organization_id)
        return PlannerInput(
            organization_id=inp.organization_id,
            context=inp.context,
            article_id=inp.article_id,
            topic=inp.topic,
            industry=inp.industry,
            target_audience_hint=inp.target_audience_hint,
            previous_post_topics=inp.previous_post_topics,
            previous_content_types=inp.previous_content_types,
            previous_ctas=inp.previous_ctas,
            previous_audiences=inp.previous_audiences,
            feedback_signals=inp.feedback_signals,
            article_metadata=inp.article_metadata,
            correlation_id=inp.correlation_id,
            relevance_score=inp.relevance_score,
            policy_id=inp.policy_id,
            topic_signals=topic_signals,
            audience_profile=audience,
            diversity=diversity,
            priority=priority,
            calendar=calendar,
        )

    async def strategy(self, inp: PlannerInput) -> StrategyDecision:
        enriched = await self._enrich(inp)
        cache_key = _strategy_cache_key(enriched)
        if self._cache is not None:
            hit = await self._cache.get(CacheNamespace.STRATEGY, cache_key)
            if hit:
                return StrategyDecision(
                    action=StrategyAction(hit["action"]),
                    recommended_type=ContentType(hit["recommended_type"]),
                    format=ContentFormat(hit["format"]),
                    confidence=float(hit["confidence"]),
                    duplicate_score=float(hit.get("duplicate_score") or 0),
                    reasons=tuple(hit.get("reasons") or ()),
                    should_merge_articles=bool(hit.get("should_merge_articles")),
                    alternatives=tuple(hit.get("alternatives") or ()),
                    metrics=dict(hit.get("metrics") or {}),
                )
        decision = await self._strategy.evaluate(enriched, self._policy)
        if self._cache is not None:
            await self._cache.set(
                CacheNamespace.STRATEGY,
                cache_key,
                {
                    "action": decision.action.value,
                    "recommended_type": decision.recommended_type.value,
                    "format": decision.format.value,
                    "confidence": decision.confidence,
                    "duplicate_score": decision.duplicate_score,
                    "reasons": list(decision.reasons),
                    "should_merge_articles": decision.should_merge_articles,
                    "alternatives": list(decision.alternatives),
                    "metrics": decision.metrics,
                },
                ttl_seconds=600,
            )
        return decision

    async def plan(self, inp: PlannerInput) -> ContentPlan:
        """Assemble candidate ContentPlan — does not validate."""
        started = time.perf_counter()
        enriched = await self._enrich(inp)
        cache_key = _planner_cache_key(enriched)
        if self._cache is not None:
            hit = await self._cache.get(CacheNamespace.PLANNER, cache_key)
            if hit and hit.get("plan"):
                return ContentPlan.from_dict(hit["plan"])

        decision = await self.strategy(enriched)
        if decision.action == StrategyAction.IGNORE:
            plan = self._rejected_plan(enriched, decision)
            planning_ms = int((time.perf_counter() - started) * 1000)
            plan = replace(
                plan,
                metrics={
                    **plan.metrics,
                    "planning_ms": planning_ms,
                    "strategy_action": decision.action.value,
                    "rejected": True,
                },
            )
            plan = await self._repo.save(plan)
            logger.info(
                "content.plan.ignored",
                extra={
                    "app_module": "content",
                    "operation": "plan",
                    "correlation_id": inp.correlation_id,
                    "outcome": "ignored",
                },
            )
            return plan

        plan = self._assemble(enriched, decision)
        planning_ms = int((time.perf_counter() - started) * 1000)
        plan = replace(
            plan,
            metrics={
                **plan.metrics,
                **decision.metrics,
                "planning_ms": planning_ms,
                "strategy_action": decision.action.value,
                "content_type": plan.content_type.value,
                "audience": plan.audience.value,
                "validated": False,
            },
        )
        plan = await self._repo.save(plan)

        if self._cache is not None:
            await self._cache.set(
                CacheNamespace.PLANNER,
                cache_key,
                {"plan": plan.to_dict()},
                ttl_seconds=600,
            )

        logger.info(
            "content.plan.created",
            extra={
                "app_module": "content",
                "operation": "plan",
                "correlation_id": inp.correlation_id,
                "outcome": "candidate",
                "duration_ms": planning_ms,
            },
        )
        return plan

    def _rejected_plan(
        self, inp: PlannerInput, decision: StrategyDecision
    ) -> ContentPlan:
        topic = inp.topic or _derive_topic(inp)
        reason = "; ".join(decision.reasons) or "strategy_ignore"
        profile = inp.audience_profile
        audience = profile.primary if profile else self._audience.resolve(inp, self._policy).primary
        explanation = PlannerExplanation(
            decision="ignore",
            evidence=decision.reasons,
            confidence_reasoning=f"confidence={decision.confidence}",
            alternatives=decision.alternatives,
        )
        return ContentPlan(
            id=uuid.uuid4(),
            organization_id=inp.organization_id,
            topic=topic,
            audience=audience,
            tone=Tone(self._policy.default_tone),
            goal=Goal(self._policy.default_goal),
            cta=CTA(self._policy.default_cta),
            content_type=decision.recommended_type,
            format=decision.format,
            strategy="do_not_create",
            hook_strategy="n/a",
            cta_strategy="n/a",
            keywords=(),
            image_style="none",
            visual_direction="none",
            slide_outline=(),
            carousel=None,
            prompt_variables={"action": "ignore"},
            confidence=decision.confidence,
            reasoning=decision.reasons,
            status=PlanStatus.IGNORED,
            article_id=inp.article_id,
            strategy_action=StrategyAction.IGNORE,
            rejected_reason=reason,
            correlation_id=inp.correlation_id,
            explanation=explanation,
            metrics=dict(decision.metrics),
        )

    def _assemble(
        self, inp: PlannerInput, decision: StrategyDecision
    ) -> ContentPlan:
        topic = inp.topic or _derive_topic(inp)
        profile: AudienceProfile = inp.audience_profile or self._audience.resolve(
            inp, self._policy
        )
        audience = profile.primary
        diversity: DiversityRecommendation | None = inp.diversity
        if diversity and diversity.recommend_alternate_audience:
            try:
                from app.modules.content.domain.models import Audience

                audience = Audience(diversity.recommend_alternate_audience)
            except ValueError:
                pass

        tone = Tone(self._policy.default_tone)
        goal = Goal(self._policy.default_goal)
        cta = CTA(self._policy.default_cta)
        if diversity and diversity.recommend_alternate_cta:
            try:
                cta = CTA(diversity.recommend_alternate_cta)
            except ValueError:
                pass

        brand = self._policy.brand_rules or {}
        if brand.get("tone"):
            try:
                tone = Tone(str(brand["tone"]))
            except ValueError:
                pass

        keywords = _keywords(topic, inp)
        slides = _slide_outline(topic, decision, self._policy)
        carousel = None
        if decision.format == ContentFormat.CAROUSEL:
            carousel = CarouselStructure(
                slide_count=len(slides),
                slides=slides,
                visual_style=str(brand.get("visual_style") or "clean_professional"),
            )

        strategy = (
            f"Create a {decision.recommended_type.value} "
            f"({decision.format.value}) for {audience.value} on '{topic}'."
        )
        hook_strategy = _hook_strategy(decision.recommended_type, tone)
        cta_strategy = f"End with a {cta.value} prompt aligned to {goal.value}."
        topic_signals: TopicSignals | None = inp.topic_signals
        framework = (
            topic_signals.framework
            if topic_signals and topic_signals.framework
            else _framework(decision.recommended_type)
        )

        priority: PrioritySignals | None = inp.priority
        calendar: CalendarContext | None = inp.calendar
        evidence = list(decision.reasons)
        if topic_signals:
            evidence.append(
                f"topic category={topic_signals.category} novelty={topic_signals.novelty_score}"
            )
        if profile:
            evidence.append(
                f"audience={profile.primary.value} conf={profile.confidence} via {profile.metadata.get('source')}"
            )
        if diversity and diversity.reasons:
            evidence.extend(diversity.reasons)
        if priority and priority.reasons:
            evidence.extend(priority.reasons)
        if calendar:
            evidence.append(
                f"calendar today={calendar.today_generated_count} frequency_ok={calendar.frequency_ok}"
            )

        explanation = PlannerExplanation(
            decision=f"create_{decision.recommended_type.value}_{decision.format.value}",
            evidence=tuple(evidence),
            confidence_reasoning=(
                f"confidence={decision.confidence} from relevance/diversity/priority/topic signals"
            ),
            alternatives=decision.alternatives,
        )

        prompt_variables = {
            "topic": topic,
            "audience": audience.value,
            "tone": tone.value,
            "goal": goal.value,
            "cta": cta.value,
            "content_type": decision.recommended_type.value,
            "format": decision.format.value,
            "keywords": list(keywords),
            "framework": framework,
            "citation_count": len(inp.context.citation_map.entries),
            "knowledge_sources": list(inp.context.knowledge_sources),
            "industry": inp.industry,
            "topic_category": topic_signals.category if topic_signals else "",
            "audience_hierarchy": list(profile.hierarchy),
        }

        return ContentPlan(
            id=uuid.uuid4(),
            organization_id=inp.organization_id,
            topic=topic,
            audience=audience,
            tone=tone,
            goal=goal,
            cta=cta,
            content_type=decision.recommended_type,
            format=decision.format,
            strategy=strategy,
            hook_strategy=hook_strategy,
            cta_strategy=cta_strategy,
            keywords=keywords,
            image_style=str(brand.get("image_style") or "branded_illustration"),
            visual_direction=_visual_direction(decision.recommended_type),
            slide_outline=slides if decision.format == ContentFormat.CAROUSEL else (),
            carousel=carousel,
            prompt_variables=prompt_variables,
            confidence=decision.confidence,
            reasoning=tuple(evidence),
            status=PlanStatus.PENDING,
            article_id=inp.article_id,
            strategy_action=StrategyAction.CREATE,
            correlation_id=inp.correlation_id,
            reading_time_minutes=min(
                self._policy.max_reading_time_minutes,
                2 if decision.format == ContentFormat.SINGLE else 3,
            ),
            difficulty="intermediate",
            framework=framework,
            explanation=explanation,
            metrics={},
        )


def _derive_topic(inp: PlannerInput) -> str:
    meta_title = (inp.article_metadata or {}).get("title")
    if meta_title:
        return str(meta_title)[:200]
    if inp.context.sections.get("knowledge"):
        return inp.context.sections["knowledge"].split("\n", 1)[0][:200]
    return (inp.context.text or "Untitled topic")[:120]


def _keywords(topic: str, inp: PlannerInput) -> tuple[str, ...]:
    tokens = [t for t in topic.lower().replace(",", " ").split() if len(t) > 3][:8]
    if inp.industry:
        tokens.append(inp.industry.lower())
    return tuple(dict.fromkeys(tokens))


def _slide_outline(
    topic: str, decision: StrategyDecision, policy: PlannerPolicy
) -> tuple[SlideOutline, ...]:
    n = max(policy.min_slide_count, min(policy.max_slide_count, policy.default_slide_count))
    templates = [
        ("Hook", "Capture attention with the core problem"),
        ("Context", "Why this matters now"),
        ("Insight", "Key takeaway from knowledge context"),
        ("Guidance", "Practical action the audience can take"),
        ("Proof", "Evidence, claim, or example cue"),
        ("Risk", "What happens if ignored"),
        ("CTA", "Invite engagement aligned to goal"),
        ("Recap", "Summarize the framework"),
        ("Resources", "Point to guide or next step"),
        ("Close", "Brand-aligned closing line cue"),
    ]
    slides = []
    for i in range(n):
        title, purpose = templates[i % len(templates)]
        slides.append(
            SlideOutline(
                index=i + 1,
                title=f"{title}: {topic[:40]}" if i == 0 else title,
                purpose=purpose,
                key_points=(decision.recommended_type.value, decision.format.value),
            )
        )
    return tuple(slides)


def _hook_strategy(content_type: ContentType, tone: Tone) -> str:
    if content_type == ContentType.SECURITY_ALERT:
        return "Lead with urgency and a concrete risk signal."
    if content_type == ContentType.COMPLIANCE_UPDATE:
        return "Lead with regulatory change and business impact."
    if content_type == ContentType.CHECKLIST:
        return "Lead with a numbered-outcome promise."
    return f"Lead with a {tone.value} curiosity gap tied to the topic."


def _framework(content_type: ContentType) -> str:
    mapping = {
        ContentType.CHECKLIST: "checklist_5_7",
        ContentType.BEST_PRACTICES: "best_practices_framework",
        ContentType.THOUGHT_LEADERSHIP: "point_evidence_implication",
        ContentType.SECURITY_ALERT: "threat_impact_action",
        ContentType.COMPLIANCE_UPDATE: "change_impact_checklist",
        ContentType.FAQ: "question_answer_series",
        ContentType.WEEKLY_ROUNDUP: "themes_takeaways_cta",
    }
    return mapping.get(content_type, "hook_value_proof_cta")


def _visual_direction(content_type: ContentType) -> str:
    if content_type == ContentType.SECURITY_ALERT:
        return "high-contrast alert visual, minimal text overlays"
    if content_type in {ContentType.CHECKLIST, ContentType.BEST_PRACTICES, ContentType.FAQ}:
        return "structured carousel slides with clear hierarchy"
    return "brand-aligned professional illustration"


def _strategy_cache_key(inp: PlannerInput) -> str:
    return (
        f"{inp.organization_id}:{inp.article_id}:{inp.topic}:"
        f"{inp.correlation_id}:strategy"
    )


def _planner_cache_key(inp: PlannerInput) -> str:
    return (
        f"{inp.organization_id}:{inp.article_id}:{inp.topic}:"
        f"{inp.correlation_id}:plan"
    )
