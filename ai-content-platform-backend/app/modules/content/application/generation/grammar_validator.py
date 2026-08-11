"""Grammar / readability heuristics (deterministic, no LLM)."""

from __future__ import annotations

import re

from app.modules.content.domain.models import (
    DraftValidationResult,
    GenerationPolicy,
    StructuredDraft,
)

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+\w+ed\b", re.IGNORECASE
)


class DefaultGrammarValidator:
    def validate(
        self, draft: StructuredDraft, policy: GenerationPolicy
    ) -> DraftValidationResult:
        text = f"{draft.hook} {draft.body}".strip()
        errors: list[str] = []
        sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
        if not sentences:
            return DraftValidationResult(
                valid=False, errors=("empty content",), grammar_score=0.0, readability_score=0.0
            )

        word_counts = [len(s.split()) for s in sentences]
        avg = sum(word_counts) / max(1, len(word_counts))
        grammar = 1.0
        readability = 1.0

        if avg > policy.max_avg_sentence_words:
            errors.append("average sentence length too high")
            grammar -= 0.2
            readability -= 0.25

        passives = len(_PASSIVE.findall(text))
        ratio = passives / max(1, len(sentences))
        if ratio > policy.max_passive_ratio:
            errors.append("excessive passive voice")
            grammar -= 0.15
            readability -= 0.1

        # Double spaces / broken formatting
        if "  " in draft.body or "\t" in draft.body:
            errors.append("formatting issues")
            grammar -= 0.05

        grammar = max(0.0, min(1.0, grammar))
        readability = max(0.0, min(1.0, readability))
        # Soft: length issues are warnings unless severe
        hard = [e for e in errors if e != "formatting issues"]
        valid = len(hard) == 0 or grammar >= 0.5
        return DraftValidationResult(
            valid=valid if not hard else grammar >= 0.4,
            errors=tuple(errors) if grammar < 0.5 else (),
            grammar_score=round(grammar, 4),
            readability_score=round(readability, 4),
        )
