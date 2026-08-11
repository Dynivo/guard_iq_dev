"""Token budget estimation and intelligent trim."""

from __future__ import annotations

from app.modules.knowledge.domain.models import KnowledgeItem


class DefaultTokenBudgetManager:
    """~4 chars/token heuristic — replaceable when provider-specific counters land."""

    def estimate(self, text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    def allocate(
        self, items: tuple[KnowledgeItem, ...], *, budget: int
    ) -> tuple[KnowledgeItem, ...]:
        return self.trim(items, budget=budget)

    def trim(
        self, items: tuple[KnowledgeItem, ...], *, budget: int
    ) -> tuple[KnowledgeItem, ...]:
        if budget <= 0:
            return ()
        kept: list[KnowledgeItem] = []
        used = 0
        # Prefer higher rank_score / similarity
        ordered = sorted(
            items,
            key=lambda i: (
                i.rank_score if i.rank_score is not None else 0.0,
                i.similarity if i.similarity is not None else 0.0,
                i.source_quality,
            ),
            reverse=True,
        )
        for item in ordered:
            cost = self.estimate(item.title) + self.estimate(item.content)
            if used + cost > budget:
                remaining = budget - used
                if remaining < 32:
                    break
                # Truncate content to fit
                max_chars = max(0, remaining * 4 - len(item.title) - 8)
                truncated = item.content[:max_chars]
                kept.append(
                    KnowledgeItem(
                        id=item.id,
                        type=item.type,
                        organization_id=item.organization_id,
                        title=item.title,
                        content=truncated,
                        metadata={**item.metadata, "truncated": True},
                        source_quality=item.source_quality,
                        confidence=item.confidence,
                        created_at=item.created_at,
                        similarity=item.similarity,
                        rank_score=item.rank_score,
                    )
                )
                break
            kept.append(item)
            used += cost
        return tuple(kept)
