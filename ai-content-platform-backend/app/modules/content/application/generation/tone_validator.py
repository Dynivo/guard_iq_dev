"""Tone validator — profile forbidden signals."""

from __future__ import annotations

from app.modules.content.domain.models import DraftValidationResult, StructuredDraft


class DefaultToneValidator:
    def validate(
        self, draft: StructuredDraft, *, expected_tone: str, profiles: dict
    ) -> DraftValidationResult:
        text = f"{draft.hook}\n{draft.body}".lower()
        profile = profiles.get(expected_tone) or profiles.get("professional") or {}
        if not isinstance(profile, dict):
            profile = {}
        errors: list[str] = []
        score = 1.0
        for signal in profile.get("forbidden_signals") or []:
            if str(signal).lower() in text:
                errors.append(f"tone mismatch ({expected_tone}): {signal}")
                score -= 0.3
        score = max(0.0, min(1.0, score))
        return DraftValidationResult(
            valid=not errors, errors=tuple(errors), tone_score=round(score, 4)
        )
