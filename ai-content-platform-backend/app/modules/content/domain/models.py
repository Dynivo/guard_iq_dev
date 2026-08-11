"""Content Planner domain models — structured strategy only (no prose)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.modules.knowledge.domain.models import OptimizedContext


class ContentType(str, Enum):
    CAROUSEL = "carousel"
    SINGLE_POST = "single_post"
    EDUCATIONAL = "educational"
    THOUGHT_LEADERSHIP = "thought_leadership"
    SECURITY_ALERT = "security_alert"
    CHECKLIST = "checklist"
    BEST_PRACTICES = "best_practices"
    CASE_STUDY = "case_study"
    SUCCESS_STORY = "success_story"
    INDUSTRY_NEWS = "industry_news"
    WEEKLY_ROUNDUP = "weekly_roundup"
    COMPLIANCE_UPDATE = "compliance_update"
    OPINION = "opinion"
    CUSTOMER_STORY = "customer_story"
    FAQ = "faq"


class Audience(str, Enum):
    BUSINESS_OWNERS = "business_owners"
    IT_MANAGERS = "it_managers"
    SECURITY_TEAMS = "security_teams"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    SMBS = "smbs"
    ENTERPRISE = "enterprise"
    DEVELOPERS = "developers"
    EXECUTIVES = "executives"


class Tone(str, Enum):
    PROFESSIONAL = "professional"
    EDUCATIONAL = "educational"
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    URGENT = "urgent"
    AUTHORITY = "authority"
    FRIENDLY = "friendly"


class Goal(str, Enum):
    EDUCATE = "educate"
    ENGAGE = "engage"
    AWARENESS = "awareness"
    LEAD_GENERATION = "lead_generation"
    TRUST_BUILDING = "trust_building"
    BRAND_POSITIONING = "brand_positioning"
    COMMUNITY = "community"


class CTA(str, Enum):
    FOLLOW = "follow"
    COMMENT = "comment"
    DOWNLOAD = "download"
    VISIT_WEBSITE = "visit_website"
    BOOK_DEMO = "book_demo"
    READ_GUIDE = "read_guide"


class ContentFormat(str, Enum):
    SINGLE = "single"
    CAROUSEL = "carousel"


class StrategyAction(str, Enum):
    CREATE = "create"
    IGNORE = "ignore"


class PlanStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class SlideOutline:
    index: int
    title: str
    purpose: str
    key_points: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CarouselStructure:
    slide_count: int
    slides: tuple[SlideOutline, ...] = ()
    visual_style: str = "clean_professional"


@dataclass(frozen=True, slots=True)
class PlannerPolicy:
    policy_id: str = "default"
    min_relevance: float = 0.3
    max_duplicate_score: float = 0.85
    min_confidence: float = 0.4
    preferred_audiences: tuple[str, ...] = ()
    preferred_content_types: tuple[str, ...] = ()
    force_carousel_types: tuple[str, ...] = (
        ContentType.CHECKLIST.value,
        ContentType.BEST_PRACTICES.value,
        ContentType.FAQ.value,
        ContentType.WEEKLY_ROUNDUP.value,
    )
    default_tone: str = Tone.PROFESSIONAL.value
    default_goal: str = Goal.EDUCATE.value
    default_cta: str = CTA.COMMENT.value
    default_audience: str = Audience.BUSINESS_OWNERS.value
    min_slide_count: int = 5
    max_slide_count: int = 10
    default_slide_count: int = 7
    max_reading_time_minutes: int = 3
    require_image_style: bool = True
    require_visual_direction: bool = True
    allowed_ctas: tuple[str, ...] = tuple(c.value for c in CTA)
    diversity_max_type_share: float = 0.5
    diversity_max_audience_share: float = 0.6
    diversity_max_cta_share: float = 0.6
    industry_rules: dict[str, Any] = field(default_factory=dict)
    organization_rules: dict[str, Any] = field(default_factory=dict)
    brand_rules: dict[str, Any] = field(default_factory=dict)
    priorities: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RecentContentHistory:
    topics: tuple[str, ...] = ()
    content_types: tuple[str, ...] = ()
    ctas: tuple[str, ...] = ()
    audiences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TopicSignals:
    novelty_score: float = 0.5
    urgency: float = 0.5
    trend_score: float = 0.5
    popularity: float = 0.5
    business_impact: float = 0.5
    seasonality: float = 0.5
    category: str = "general"
    framework: str = "hook_value_proof_cta"


@dataclass(frozen=True, slots=True)
class AudienceProfile:
    primary: Audience
    confidence: float
    hierarchy: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiversityRecommendation:
    repetition_score: float = 0.0
    recommend_alternate_type: str | None = None
    recommend_alternate_cta: str | None = None
    recommend_alternate_audience: str | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CalendarContext:
    """Future calendar awareness — stub defaults only."""

    today_generated_count: int = 0
    weekly_schedule: tuple[str, ...] = ()
    frequency_ok: bool = True
    upcoming_events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrioritySignals:
    score: float = 0.5
    industry_weight: float = 0.5
    framework_weight: float = 0.5
    compliance_weight: float = 0.5
    brand_weight: float = 0.5
    preferred_type: str | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlannerExplanation:
    decision: str = ""
    evidence: tuple[str, ...] = ()
    confidence_reasoning: str = ""
    alternatives: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "evidence": list(self.evidence),
            "confidence_reasoning": self.confidence_reasoning,
            "alternatives": list(self.alternatives),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> PlannerExplanation:
        if not data:
            return PlannerExplanation()
        return PlannerExplanation(
            decision=str(data.get("decision") or ""),
            evidence=tuple(data.get("evidence") or ()),
            confidence_reasoning=str(data.get("confidence_reasoning") or ""),
            alternatives=tuple(data.get("alternatives") or ()),
        )


@dataclass(frozen=True, slots=True)
class PlannerInput:
    organization_id: uuid.UUID
    context: OptimizedContext
    article_id: uuid.UUID | None = None
    topic: str = ""
    industry: str = ""
    target_audience_hint: str = ""
    previous_post_topics: tuple[str, ...] = ()
    previous_content_types: tuple[str, ...] = ()
    previous_ctas: tuple[str, ...] = ()
    previous_audiences: tuple[str, ...] = ()
    feedback_signals: dict[str, Any] = field(default_factory=dict)
    article_metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    relevance_score: float | None = None
    policy_id: str = "default"
    topic_signals: TopicSignals | None = None
    audience_profile: AudienceProfile | None = None
    diversity: DiversityRecommendation | None = None
    priority: PrioritySignals | None = None
    calendar: CalendarContext | None = None


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    action: StrategyAction
    recommended_type: ContentType
    format: ContentFormat
    confidence: float
    duplicate_score: float = 0.0
    reasons: tuple[str, ...] = ()
    should_merge_articles: bool = False
    alternatives: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentPlan:
    """Structured content strategy — never LinkedIn post prose."""

    id: uuid.UUID
    organization_id: uuid.UUID
    topic: str
    audience: Audience
    tone: Tone
    goal: Goal
    cta: CTA
    content_type: ContentType
    format: ContentFormat
    strategy: str
    hook_strategy: str
    cta_strategy: str
    keywords: tuple[str, ...]
    image_style: str
    visual_direction: str
    slide_outline: tuple[SlideOutline, ...]
    carousel: CarouselStructure | None
    prompt_variables: dict[str, Any]
    confidence: float
    reasoning: tuple[str, ...]
    status: PlanStatus
    article_id: uuid.UUID | None = None
    strategy_action: StrategyAction = StrategyAction.CREATE
    rejected_reason: str = ""
    correlation_id: str = ""
    reading_time_minutes: int = 2
    difficulty: str = "intermediate"
    framework: str = ""
    explanation: PlannerExplanation = field(default_factory=PlannerExplanation)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "article_id": str(self.article_id) if self.article_id else None,
            "topic": self.topic,
            "audience": self.audience.value,
            "tone": self.tone.value,
            "goal": self.goal.value,
            "cta": self.cta.value,
            "content_type": self.content_type.value,
            "format": self.format.value,
            "strategy": self.strategy,
            "hook_strategy": self.hook_strategy,
            "cta_strategy": self.cta_strategy,
            "keywords": list(self.keywords),
            "image_style": self.image_style,
            "visual_direction": self.visual_direction,
            "slide_outline": [
                {
                    "index": s.index,
                    "title": s.title,
                    "purpose": s.purpose,
                    "key_points": list(s.key_points),
                }
                for s in self.slide_outline
            ],
            "carousel": None
            if self.carousel is None
            else {
                "slide_count": self.carousel.slide_count,
                "visual_style": self.carousel.visual_style,
                "slides": [
                    {
                        "index": s.index,
                        "title": s.title,
                        "purpose": s.purpose,
                        "key_points": list(s.key_points),
                    }
                    for s in self.carousel.slides
                ],
            },
            "prompt_variables": dict(self.prompt_variables),
            "confidence": self.confidence,
            "reasoning": list(self.reasoning),
            "explanation": self.explanation.to_dict(),
            "status": self.status.value,
            "strategy_action": self.strategy_action.value,
            "rejected_reason": self.rejected_reason,
            "correlation_id": self.correlation_id,
            "reading_time_minutes": self.reading_time_minutes,
            "difficulty": self.difficulty,
            "framework": self.framework,
            "metrics": dict(self.metrics),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ContentPlan:
        slides_raw = data.get("slide_outline") or []
        slides = tuple(
            SlideOutline(
                index=int(s.get("index", i + 1)),
                title=str(s.get("title") or ""),
                purpose=str(s.get("purpose") or ""),
                key_points=tuple(s.get("key_points") or ()),
            )
            for i, s in enumerate(slides_raw)
        )
        car_raw = data.get("carousel")
        carousel = None
        if car_raw:
            c_slides = tuple(
                SlideOutline(
                    index=int(s.get("index", i + 1)),
                    title=str(s.get("title") or ""),
                    purpose=str(s.get("purpose") or ""),
                    key_points=tuple(s.get("key_points") or ()),
                )
                for i, s in enumerate(car_raw.get("slides") or [])
            )
            carousel = CarouselStructure(
                slide_count=int(car_raw.get("slide_count") or len(c_slides) or 5),
                slides=c_slides or slides,
                visual_style=str(car_raw.get("visual_style") or "clean_professional"),
            )
        article_id = data.get("article_id")
        reasoning = tuple(data.get("reasoning") or ())
        explanation = PlannerExplanation.from_dict(data.get("explanation"))
        if not explanation.evidence and reasoning:
            explanation = PlannerExplanation(
                decision=explanation.decision or str(data.get("strategy") or ""),
                evidence=reasoning,
                confidence_reasoning=explanation.confidence_reasoning,
                alternatives=explanation.alternatives,
            )
        return ContentPlan(
            id=uuid.UUID(str(data["id"])) if data.get("id") else uuid.uuid4(),
            organization_id=uuid.UUID(str(data["organization_id"])),
            topic=str(data.get("topic") or ""),
            audience=Audience(str(data.get("audience") or Audience.BUSINESS_OWNERS.value)),
            tone=Tone(str(data.get("tone") or Tone.PROFESSIONAL.value)),
            goal=Goal(str(data.get("goal") or Goal.EDUCATE.value)),
            cta=CTA(str(data.get("cta") or CTA.COMMENT.value)),
            content_type=ContentType(
                str(data.get("content_type") or ContentType.SINGLE_POST.value)
            ),
            format=ContentFormat(str(data.get("format") or ContentFormat.SINGLE.value)),
            strategy=str(data.get("strategy") or ""),
            hook_strategy=str(data.get("hook_strategy") or ""),
            cta_strategy=str(data.get("cta_strategy") or ""),
            keywords=tuple(data.get("keywords") or ()),
            image_style=str(data.get("image_style") or "branded_illustration"),
            visual_direction=str(data.get("visual_direction") or ""),
            slide_outline=slides,
            carousel=carousel,
            prompt_variables=dict(data.get("prompt_variables") or {}),
            confidence=float(data.get("confidence") or 0.0),
            reasoning=reasoning,
            status=PlanStatus(str(data.get("status") or PlanStatus.PENDING.value)),
            article_id=uuid.UUID(str(article_id)) if article_id else None,
            strategy_action=StrategyAction(
                str(data.get("strategy_action") or StrategyAction.CREATE.value)
            ),
            rejected_reason=str(data.get("rejected_reason") or ""),
            correlation_id=str(data.get("correlation_id") or ""),
            reading_time_minutes=int(data.get("reading_time_minutes") or 2),
            difficulty=str(data.get("difficulty") or "intermediate"),
            framework=str(data.get("framework") or ""),
            explanation=explanation,
            metrics=dict(data.get("metrics") or {}),
        )


# --- M9 Content Generation Engine domain ---


class DraftLifecycleStatus(str, Enum):
    GENERATED = "generated"
    VALIDATED = "validated"
    FORMATTED = "formatted"
    FINALIZED = "finalized"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DraftSlide:
    index: int
    title: str
    body: str = ""


@dataclass(frozen=True, slots=True)
class RawAIOutput:
    text: str
    response_format: str = "json"
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "response_format": self.response_format,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "cost_estimate": self.cost_estimate,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class StructuredDraft:
    hook: str = ""
    body: str = ""
    cta: str = ""
    hashtags: tuple[str, ...] = ()
    sections: dict[str, str] = field(default_factory=dict)
    slides: tuple[DraftSlide, ...] = ()
    format: str = ContentFormat.SINGLE.value
    content_type: str = ContentType.SINGLE_POST.value
    platform: str = "linkedin"
    lifecycle_status: str = DraftLifecycleStatus.GENERATED.value
    quality_score: float = 0.0
    confidence_score: float = 0.0
    grammar_score: float = 0.0
    brand_score: float = 0.0
    fact_score: float = 0.0
    tone_score: float = 0.0
    readability_score: float = 0.0
    content_plan_id: str = ""
    prompt_version: str = ""
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    markdown: str = ""
    quality: Any = None  # QualityBreakdown | None — set after class defined
    visual_brief: Any = None
    safety: Any = None
    draft_metadata: Any = None

    def to_dict(self) -> dict[str, Any]:
        q = self.quality
        vb = self.visual_brief
        sf = self.safety
        dm = self.draft_metadata
        return {
            "hook": self.hook,
            "body": self.body,
            "cta": self.cta,
            "hashtags": list(self.hashtags),
            "sections": dict(self.sections),
            "slides": [
                {"index": s.index, "title": s.title, "body": s.body} for s in self.slides
            ],
            "format": self.format,
            "content_type": self.content_type,
            "platform": self.platform,
            "lifecycle_status": self.lifecycle_status,
            "quality_score": self.quality_score,
            "confidence_score": self.confidence_score,
            "grammar_score": self.grammar_score,
            "brand_score": self.brand_score,
            "fact_score": self.fact_score,
            "tone_score": self.tone_score,
            "readability_score": self.readability_score,
            "content_plan_id": self.content_plan_id,
            "prompt_version": self.prompt_version,
            "provider_metadata": dict(self.provider_metadata),
            "metadata": dict(self.metadata),
            "markdown": self.markdown,
            "quality": q.to_dict() if q is not None and hasattr(q, "to_dict") else q,
            "visual_brief": vb.to_dict() if vb is not None and hasattr(vb, "to_dict") else vb,
            "safety": sf.to_dict() if sf is not None and hasattr(sf, "to_dict") else sf,
            "draft_metadata": (
                dm.to_dict() if dm is not None and hasattr(dm, "to_dict") else dm
            ),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> StructuredDraft:
        slides = tuple(
            DraftSlide(
                index=int(s.get("index", i + 1)),
                title=str(s.get("title") or ""),
                body=str(s.get("body") or ""),
            )
            for i, s in enumerate(data.get("slides") or [])
        )
        return StructuredDraft(
            hook=str(data.get("hook") or ""),
            body=str(data.get("body") or ""),
            cta=str(data.get("cta") or ""),
            hashtags=tuple(data.get("hashtags") or ()),
            sections=dict(data.get("sections") or {}),
            slides=slides,
            format=str(data.get("format") or ContentFormat.SINGLE.value),
            content_type=str(data.get("content_type") or ContentType.SINGLE_POST.value),
            platform=str(data.get("platform") or "linkedin"),
            lifecycle_status=str(
                data.get("lifecycle_status") or DraftLifecycleStatus.GENERATED.value
            ),
            quality_score=float(data.get("quality_score") or 0.0),
            confidence_score=float(data.get("confidence_score") or 0.0),
            grammar_score=float(data.get("grammar_score") or 0.0),
            brand_score=float(data.get("brand_score") or 0.0),
            fact_score=float(data.get("fact_score") or 0.0),
            tone_score=float(data.get("tone_score") or 0.0),
            readability_score=float(data.get("readability_score") or 0.0),
            content_plan_id=str(data.get("content_plan_id") or ""),
            prompt_version=str(data.get("prompt_version") or ""),
            provider_metadata=dict(data.get("provider_metadata") or {}),
            metadata=dict(data.get("metadata") or {}),
            markdown=str(data.get("markdown") or ""),
            quality=data.get("quality"),
            visual_brief=data.get("visual_brief"),
            safety=data.get("safety"),
            draft_metadata=data.get("draft_metadata"),
        )


@dataclass(frozen=True, slots=True)
class DraftValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    content_score: float = 1.0
    fact_score: float = 1.0
    brand_score: float = 1.0
    tone_score: float = 1.0
    grammar_score: float = 1.0
    readability_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "content_score": self.content_score,
            "fact_score": self.fact_score,
            "brand_score": self.brand_score,
            "tone_score": self.tone_score,
            "grammar_score": self.grammar_score,
            "readability_score": self.readability_score,
        }


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Input to the Content Generation Engine — PromptRequest required."""

    prompt_request: Any  # PromptRequest — avoid circular import at domain layer
    content_plan_id: str = ""
    content_plan: dict[str, Any] = field(default_factory=dict)
    source_text: str = ""
    organization_id: uuid.UUID | None = None
    correlation_id: str = ""
    expected_tone: str = Tone.PROFESSIONAL.value
    content_type: str = ContentType.SINGLE_POST.value
    format: str = ContentFormat.SINGLE.value
    brand_preferences: dict[str, Any] = field(default_factory=dict)
    context_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GenerationResult:
    success: bool
    draft: StructuredDraft | None = None
    validation: DraftValidationResult | None = None
    raw: RawAIOutput | None = None
    replay_id: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    quality: Any = None
    safety: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "draft": self.draft.to_dict() if self.draft else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "raw": self.raw.to_dict() if self.raw else None,
            "replay_id": self.replay_id,
            "metrics": dict(self.metrics),
            "errors": list(self.errors),
            "quality": (
                self.quality.to_dict()
                if self.quality is not None and hasattr(self.quality, "to_dict")
                else self.quality
            ),
            "safety": (
                self.safety.to_dict()
                if self.safety is not None and hasattr(self.safety, "to_dict")
                else self.safety
            ),
        }


@dataclass(frozen=True, slots=True)
class DraftVersionSnapshot:
    draft_id: str
    version: int
    text: str
    draft_json: dict[str, Any] = field(default_factory=dict)
    change_summary: str = ""


@dataclass(frozen=True, slots=True)
class GenerationReplayRecord:
    replay_id: str
    prompt_request_json: dict[str, Any]
    raw_output: str
    draft_json: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
    draft_id: str = ""
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class DraftDiff:
    left_version: int
    right_version: int
    changes: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_version": self.left_version,
            "right_version": self.right_version,
            "changes": list(self.changes),
        }


@dataclass(frozen=True, slots=True)
class GenerationPolicy:
    max_hook_chars: int = 200
    max_body_chars: int = 3000
    max_cta_chars: int = 300
    min_hook_chars: int = 10
    min_body_chars: int = 40
    require_cta: bool = True
    require_hashtags: bool = False
    max_hashtags: int = 8
    min_carousel_slides: int = 3
    max_carousel_slides: int = 12
    min_quality_score: float = 0.45
    forbidden_phrases: tuple[str, ...] = ()
    preferred_vocabulary: tuple[str, ...] = ()
    tone_profiles: dict[str, Any] = field(default_factory=dict)
    max_avg_sentence_words: int = 28
    max_passive_ratio: float = 0.45


# --- M9r refinements ---


class RegenSection(str, Enum):
    FULL = "full"
    HOOK = "hook"
    BODY = "body"
    CTA = "cta"
    HASHTAGS = "hashtags"
    CAROUSEL = "carousel"
    SUMMARY = "summary"


@dataclass(frozen=True, slots=True)
class VisualBrief:
    illustration_style: str = ""
    scene: str = ""
    composition: str = ""
    focal_point: str = ""
    camera_angle: str = ""
    icon_suggestions: tuple[str, ...] = ()
    infographic_suggestions: tuple[str, ...] = ()
    negative_prompt: str = ""
    typography_safe_area: str = ""
    color_palette: tuple[str, ...] = ()
    visual_hierarchy: str = ""
    emotion: str = ""
    visual_intent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "illustration_style": self.illustration_style,
            "scene": self.scene,
            "composition": self.composition,
            "focal_point": self.focal_point,
            "camera_angle": self.camera_angle,
            "icon_suggestions": list(self.icon_suggestions),
            "infographic_suggestions": list(self.infographic_suggestions),
            "negative_prompt": self.negative_prompt,
            "typography_safe_area": self.typography_safe_area,
            "color_palette": list(self.color_palette),
            "visual_hierarchy": self.visual_hierarchy,
            "emotion": self.emotion,
            "visual_intent": self.visual_intent,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualBrief:
        if not data:
            return VisualBrief()
        return VisualBrief(
            illustration_style=str(data.get("illustration_style") or ""),
            scene=str(data.get("scene") or ""),
            composition=str(data.get("composition") or ""),
            focal_point=str(data.get("focal_point") or ""),
            camera_angle=str(data.get("camera_angle") or ""),
            icon_suggestions=tuple(data.get("icon_suggestions") or ()),
            infographic_suggestions=tuple(data.get("infographic_suggestions") or ()),
            negative_prompt=str(data.get("negative_prompt") or ""),
            typography_safe_area=str(data.get("typography_safe_area") or ""),
            color_palette=tuple(data.get("color_palette") or ()),
            visual_hierarchy=str(data.get("visual_hierarchy") or ""),
            emotion=str(data.get("emotion") or ""),
            visual_intent=str(data.get("visual_intent") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class QualityBreakdown:
    grammar: float = 0.0
    readability: float = 0.0
    brand: float = 0.0
    fact: float = 0.0
    tone: float = 0.0
    engagement: float = 0.0
    originality: float = 0.0
    structure: float = 0.0

    def composite(self) -> float:
        vals = (
            self.grammar,
            self.readability,
            self.brand,
            self.fact,
            self.tone,
            self.engagement,
            self.originality,
            self.structure,
        )
        return round(sum(vals) / len(vals), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "grammar": self.grammar,
            "readability": self.readability,
            "brand": self.brand,
            "fact": self.fact,
            "tone": self.tone,
            "engagement": self.engagement,
            "originality": self.originality,
            "structure": self.structure,
            "composite": self.composite(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> QualityBreakdown:
        if not data:
            return QualityBreakdown()
        return QualityBreakdown(
            grammar=float(data.get("grammar") or 0.0),
            readability=float(data.get("readability") or 0.0),
            brand=float(data.get("brand") or 0.0),
            fact=float(data.get("fact") or 0.0),
            tone=float(data.get("tone") or 0.0),
            engagement=float(data.get("engagement") or 0.0),
            originality=float(data.get("originality") or 0.0),
            structure=float(data.get("structure") or 0.0),
        )


@dataclass(frozen=True, slots=True)
class ContentSafetyResult:
    safe: bool = True
    hallucination_risk: bool = False
    unsafe_claims: bool = False
    compliance_warnings: bool = False
    sensitive_language: bool = False
    legal_flags: bool = False
    reasons: tuple[str, ...] = ()
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "hallucination_risk": self.hallucination_risk,
            "unsafe_claims": self.unsafe_claims,
            "compliance_warnings": self.compliance_warnings,
            "sensitive_language": self.sensitive_language,
            "legal_flags": self.legal_flags,
            "reasons": list(self.reasons),
            "score": self.score,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> ContentSafetyResult:
        if not data:
            return ContentSafetyResult()
        return ContentSafetyResult(
            safe=bool(data.get("safe", True)),
            hallucination_risk=bool(data.get("hallucination_risk")),
            unsafe_claims=bool(data.get("unsafe_claims")),
            compliance_warnings=bool(data.get("compliance_warnings")),
            sensitive_language=bool(data.get("sensitive_language")),
            legal_flags=bool(data.get("legal_flags")),
            reasons=tuple(data.get("reasons") or ()),
            score=float(data.get("score") or 1.0),
        )


@dataclass(frozen=True, slots=True)
class DraftMetadata:
    entities: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    trend_score: float = 0.0
    opportunity_types: tuple[str, ...] = ()
    audience: str = ""
    planner_decisions: dict[str, Any] = field(default_factory=dict)
    prompt_version: str = ""
    generation_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": list(self.entities),
            "topics": list(self.topics),
            "trend_score": self.trend_score,
            "opportunity_types": list(self.opportunity_types),
            "audience": self.audience,
            "planner_decisions": dict(self.planner_decisions),
            "prompt_version": self.prompt_version,
            "generation_metadata": dict(self.generation_metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DraftMetadata:
        if not data:
            return DraftMetadata()
        return DraftMetadata(
            entities=tuple(data.get("entities") or ()),
            topics=tuple(data.get("topics") or ()),
            trend_score=float(data.get("trend_score") or 0.0),
            opportunity_types=tuple(data.get("opportunity_types") or ()),
            audience=str(data.get("audience") or ""),
            planner_decisions=dict(data.get("planner_decisions") or {}),
            prompt_version=str(data.get("prompt_version") or ""),
            generation_metadata=dict(data.get("generation_metadata") or {}),
        )
