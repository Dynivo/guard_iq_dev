"""Context Builder ports."""

from __future__ import annotations

from typing import Protocol

from app.modules.context.domain.models import ContextBuildInput
from app.modules.knowledge.domain.models import KnowledgeItem, OptimizedContext


class TokenBudgetManager(Protocol):
    def estimate(self, text: str) -> int: ...

    def allocate(
        self, items: tuple[KnowledgeItem, ...], *, budget: int
    ) -> tuple[KnowledgeItem, ...]: ...

    def trim(self, items: tuple[KnowledgeItem, ...], *, budget: int) -> tuple[KnowledgeItem, ...]: ...


class ContextBuilder(Protocol):
    async def build(self, inp: ContextBuildInput) -> OptimizedContext: ...
