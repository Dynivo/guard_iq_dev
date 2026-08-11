"""Extractive knowledge compressor — token reduction only (non-LLM)."""

from __future__ import annotations

import time

from app.modules.context.application.token_budget import DefaultTokenBudgetManager
from app.modules.knowledge.domain.models import CompressedKnowledge, FilteredKnowledge


class ExtractiveCompressor:
    def __init__(self) -> None:
        self._budget = DefaultTokenBudgetManager()

    async def compress(
        self, filtered: FilteredKnowledge, *, token_budget: int
    ) -> CompressedKnowledge:
        started = time.perf_counter()
        before = sum(
            self._budget.estimate(i.title) + self._budget.estimate(i.content)
            for i in filtered.items
        )
        trimmed = self._budget.trim(filtered.items, budget=token_budget)
        after = sum(
            self._budget.estimate(i.title) + self._budget.estimate(i.content)
            for i in trimmed
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return CompressedKnowledge(
            items=trimmed,
            tokens_before=before,
            tokens_after=after,
            duration_ms=duration_ms,
        )
