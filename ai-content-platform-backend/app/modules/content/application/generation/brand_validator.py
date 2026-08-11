"""Brand validator — forbidden phrases, vocabulary, preferences."""

from __future__ import annotations

from app.modules.content.domain.models import (
    DraftValidationResult,
    GenerationPolicy,
    StructuredDraft,
)


class DefaultBrandValidator:
    def validate(
        self,
        draft: StructuredDraft,
        *,
        policy: GenerationPolicy,
        preferences: dict | None = None,
    ) -> DraftValidationResult:
        text = f"{draft.hook}\n{draft.body}\n{draft.cta}".lower()
        errors: list[str] = []
        score = 1.0
        prefs = preferences or {}

        forbidden = list(policy.forbidden_phrases) + list(
            prefs.get("forbidden_phrases") or []
        )
        for phrase in forbidden:
            if phrase and phrase.lower() in text:
                errors.append(f"forbidden phrase: {phrase}")
                score -= 0.25

        preferred = list(policy.preferred_vocabulary) + list(
            prefs.get("preferred_vocabulary") or []
        )
        if preferred:
            hits = sum(1 for p in preferred if p.lower() in text)
            if hits == 0:
                score -= 0.1  # soft preference, not hard fail

        writing_prefs = prefs.get("writing_preferences") or {}
        if isinstance(writing_prefs, dict):
            for phrase in writing_prefs.get("avoid") or []:
                if str(phrase).lower() in text:
                    errors.append(f"writing preference avoid: {phrase}")
                    score -= 0.15

        score = max(0.0, min(1.0, score))
        return DraftValidationResult(
            valid=not errors, errors=tuple(errors), brand_score=round(score, 4)
        )
