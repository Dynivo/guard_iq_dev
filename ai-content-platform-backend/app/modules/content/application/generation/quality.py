"""Independent quality dimension scoring."""

from __future__ import annotations

import re

from app.modules.content.domain.models import (
    ContentFormat,
    DraftValidationResult,
    QualityBreakdown,
    StructuredDraft,
)


class DefaultQualityBreakdownBuilder:
    def build(
        self,
        draft: StructuredDraft,
        validation: DraftValidationResult,
        *,
        source_text: str = "",
    ) -> QualityBreakdown:
        engagement = _engagement(draft)
        originality = _originality(draft, source_text)
        structure = _structure(draft, validation.content_score)
        return QualityBreakdown(
            grammar=round(validation.grammar_score, 4),
            readability=round(validation.readability_score, 4),
            brand=round(validation.brand_score, 4),
            fact=round(validation.fact_score, 4),
            tone=round(validation.tone_score, 4),
            engagement=round(engagement, 4),
            originality=round(originality, 4),
            structure=round(structure, 4),
        )


def _engagement(draft: StructuredDraft) -> float:
    score = 0.4
    if draft.hook and len(draft.hook) >= 20:
        score += 0.2
    if draft.cta and len(draft.cta) >= 8:
        score += 0.2
    if draft.hashtags:
        score += min(0.15, 0.05 * len(draft.hashtags))
    if "?" in draft.hook or "?" in draft.cta:
        score += 0.05
    return min(1.0, score)


def _originality(draft: StructuredDraft, source_text: str) -> float:
    if not source_text.strip():
        return 0.7
    body_tokens = set(re.findall(r"[a-z0-9]+", draft.body.lower()))
    src_tokens = set(re.findall(r"[a-z0-9]+", source_text.lower()))
    if not body_tokens:
        return 0.3
    overlap = len(body_tokens & src_tokens) / max(1, len(body_tokens))
    # Prefer some grounding without near-copy
    if overlap > 0.85:
        return 0.35
    if overlap < 0.05:
        return 0.55
    return min(1.0, 0.5 + (0.5 - abs(0.4 - overlap)))


def _structure(draft: StructuredDraft, content_score: float) -> float:
    score = content_score * 0.6
    if draft.hook and draft.body and draft.cta:
        score += 0.25
    if draft.format == ContentFormat.CAROUSEL.value:
        if len(draft.slides) >= 3:
            score += 0.15
        else:
            score -= 0.2
    else:
        score += 0.1
    return max(0.0, min(1.0, score))
