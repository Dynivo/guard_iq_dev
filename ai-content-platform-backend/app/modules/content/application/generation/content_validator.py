"""Content structure validator for StructuredDraft."""

from __future__ import annotations

from app.modules.content.domain.models import (
    ContentFormat,
    DraftValidationResult,
    GenerationPolicy,
    StructuredDraft,
)


class DefaultContentDraftValidator:
    def validate(
        self, draft: StructuredDraft, policy: GenerationPolicy
    ) -> DraftValidationResult:
        errors: list[str] = []
        score = 1.0

        if len(draft.hook) < policy.min_hook_chars:
            errors.append("hook too short")
            score -= 0.2
        if len(draft.hook) > policy.max_hook_chars:
            errors.append("hook exceeds max length")
            score -= 0.15
        if len(draft.body) < policy.min_body_chars:
            errors.append("body too short")
            score -= 0.25
        if len(draft.body) > policy.max_body_chars:
            errors.append("body exceeds max length")
            score -= 0.15
        if policy.require_cta and not draft.cta.strip():
            errors.append("cta required")
            score -= 0.2
        if len(draft.cta) > policy.max_cta_chars:
            errors.append("cta exceeds max length")
            score -= 0.1
        if policy.require_hashtags and not draft.hashtags:
            errors.append("hashtags required")
            score -= 0.1
        if len(draft.hashtags) > policy.max_hashtags:
            errors.append("too many hashtags")
            score -= 0.1

        if draft.format == ContentFormat.CAROUSEL.value:
            n = len(draft.slides)
            if n < policy.min_carousel_slides:
                errors.append("carousel has too few slides")
                score -= 0.25
            if n > policy.max_carousel_slides:
                errors.append("carousel has too many slides")
                score -= 0.15
            for s in draft.slides:
                if not s.title.strip():
                    errors.append(f"slide {s.index} missing title")
                    score -= 0.05

        # Hook quality: avoid all-caps spam
        if draft.hook and draft.hook.isupper() and len(draft.hook) > 12:
            errors.append("hook quality: all-caps")
            score -= 0.1

        score = max(0.0, min(1.0, score))
        return DraftValidationResult(
            valid=not errors, errors=tuple(errors), content_score=round(score, 4)
        )
