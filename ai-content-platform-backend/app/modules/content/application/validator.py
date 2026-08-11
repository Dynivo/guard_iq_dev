"""Independent Content Validator — planner never validates itself."""

from __future__ import annotations

from app.modules.content.domain.models import (
    ContentFormat,
    ContentPlan,
    PlanStatus,
    PlannerPolicy,
    StrategyAction,
    ValidationResult,
)

# Compat export
DefaultPlanValidator = None  # set below


class DefaultContentValidator:
    def validate(self, plan: ContentPlan, policy: PlannerPolicy) -> ValidationResult:
        errors: list[str] = []

        if plan.strategy_action == StrategyAction.IGNORE:
            if plan.status not in {PlanStatus.IGNORED, PlanStatus.REJECTED}:
                errors.append("ignored plans must have ignored/rejected status")
            return ValidationResult(valid=len(errors) == 0, errors=tuple(errors))

        # Required fields
        if not plan.topic.strip():
            errors.append("topic required")
        if not plan.strategy.strip():
            errors.append("strategy required")
        if not plan.hook_strategy.strip():
            errors.append("hook_strategy required")
        if not plan.cta_strategy.strip():
            errors.append("cta_strategy required")
        if not plan.prompt_variables:
            errors.append("prompt_variables required for Prompt Builder handoff")

        # CTA
        if plan.cta.value not in policy.allowed_ctas:
            errors.append(f"cta {plan.cta.value} not in allowed_ctas")
        if not plan.cta_strategy or plan.cta_strategy == "n/a":
            errors.append("cta_strategy invalid")

        # Confidence
        if plan.confidence < policy.min_confidence:
            errors.append(
                f"confidence {plan.confidence} below policy min {policy.min_confidence}"
            )

        # Image requirements
        if policy.require_image_style and (
            not plan.image_style.strip() or plan.image_style == "none"
        ):
            errors.append("image_style required")
        if policy.require_visual_direction and (
            not plan.visual_direction.strip() or plan.visual_direction == "none"
        ):
            errors.append("visual_direction required")

        # Carousel structure
        if plan.format == ContentFormat.CAROUSEL:
            if plan.carousel is None:
                errors.append("carousel structure required for carousel format")
            else:
                if plan.carousel.slide_count < policy.min_slide_count:
                    errors.append("slide_count below policy min")
                if plan.carousel.slide_count > policy.max_slide_count:
                    errors.append("slide_count above policy max")
                if not plan.carousel.slides and not plan.slide_outline:
                    errors.append("slide outline required for carousel")
                if plan.carousel.slides and len(plan.carousel.slides) != plan.carousel.slide_count:
                    errors.append("carousel slide_count mismatch")

        if plan.reading_time_minutes > policy.max_reading_time_minutes:
            errors.append("reading_time exceeds policy max")

        # Business / policy compliance
        if (
            policy.preferred_content_types
            and plan.content_type.value not in policy.preferred_content_types
            and plan.content_type.value not in policy.force_carousel_types
        ):
            # Soft: only flag if brand_rules require preferred types
            if (policy.brand_rules or {}).get("enforce_preferred_types"):
                errors.append("content_type outside preferred_content_types")

        if policy.organization_rules.get("require_explanation"):
            if not plan.explanation.decision and not plan.reasoning:
                errors.append("planner explanation required by organization_rules")

        return ValidationResult(valid=len(errors) == 0, errors=tuple(errors))


DefaultPlanValidator = DefaultContentValidator  # type: ignore[misc,assignment]
