"""Fact validator — deterministic claims/numbers vs source text."""

from __future__ import annotations

import re

from app.modules.content.domain.models import DraftValidationResult, StructuredDraft

_NUMBER = re.compile(
    r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?",
)
_TRIVIAL = {"1", "2", "3", "4", "5", "10", "100", "0"}


class DefaultFactValidator:
    def validate(
        self, draft: StructuredDraft, *, source_text: str = ""
    ) -> DraftValidationResult:
        text = f"{draft.hook}\n{draft.body}\n{draft.cta}"
        numbers = {n for n in _NUMBER.findall(text) if n not in _TRIVIAL}
        if not numbers:
            return DraftValidationResult(valid=True, fact_score=1.0)

        source_nums = set(_NUMBER.findall(source_text)) if source_text else set()
        # Citations in draft metadata
        citations = draft.metadata.get("citations") or []
        cite_blob = " ".join(str(c) for c in citations)
        source_nums |= set(_NUMBER.findall(cite_blob))

        flagged = sorted(n for n in numbers if n not in source_nums)
        if not source_text:
            # Without source, soft-pass but lower score when many numbers present
            score = max(0.5, 1.0 - 0.05 * len(numbers))
            return DraftValidationResult(
                valid=True,
                errors=(),
                fact_score=round(score, 4),
            )

        if flagged:
            return DraftValidationResult(
                valid=False,
                errors=(f"unverified numbers: {', '.join(flagged[:5])}",),
                fact_score=round(max(0.0, 1.0 - 0.2 * len(flagged)), 4),
            )
        return DraftValidationResult(valid=True, fact_score=1.0)
