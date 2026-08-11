"""Default Context Builder — assembles OptimizedContext + CitationMap."""

from __future__ import annotations

from app.modules.context.application.token_budget import DefaultTokenBudgetManager
from app.modules.context.domain.models import ContextBuildInput
from app.modules.context.domain.ports import TokenBudgetManager
from app.modules.knowledge.domain.models import (
    CitationEntry,
    CitationMap,
    KnowledgeType,
    OptimizedContext,
)


class DefaultContextBuilder:
    def __init__(self, token_budget: TokenBudgetManager | None = None) -> None:
        self._budget = token_budget or DefaultTokenBudgetManager()

    async def build(self, inp: ContextBuildInput) -> OptimizedContext:
        budget = inp.query.token_budget
        reserved = 0
        sections: dict[str, str] = {}
        if inp.brand_text:
            sections["brand"] = inp.brand_text
            reserved += self._budget.estimate(inp.brand_text)
        if inp.rules_text:
            sections["rules"] = inp.rules_text
            reserved += self._budget.estimate(inp.rules_text)
        if inp.examples_text:
            sections["examples"] = inp.examples_text
            reserved += self._budget.estimate(inp.examples_text)
        if inp.claims_text:
            sections["claims"] = inp.claims_text
            reserved += self._budget.estimate(inp.claims_text)
        if inp.preferences_text:
            sections["preferences"] = inp.preferences_text
            reserved += self._budget.estimate(inp.preferences_text)
        if inp.planner_output:
            sections["planner"] = inp.planner_output
            reserved += self._budget.estimate(inp.planner_output)
        for key, val in inp.extra_sections.items():
            sections[key] = val
            reserved += self._budget.estimate(val)

        remaining = max(256, budget - reserved)
        knowledge_items = self._budget.trim(inp.compressed.items, budget=remaining)

        knowledge_block_parts: list[str] = []
        citation_entries: list[CitationEntry] = []
        sources: list[str] = []
        for idx, item in enumerate(knowledge_items, start=1):
            knowledge_block_parts.append(
                f"[{item.type.value}:{item.id}] {item.title}\n{item.content}"
            )
            source = item.source_name or item.type.value
            if source and source not in sources:
                sources.append(source)
            citation_entries.append(
                CitationEntry(
                    citation_id=f"c{idx}",
                    knowledge_id=item.id,
                    type=item.type.value,
                    title=item.title,
                    source=source,
                    rank_score=item.rank_score,
                    snippet=item.content[:240],
                )
            )

        # Section-sourced citations (brand/rules/etc. already in sections text)
        for key, label in (
            ("brand", KnowledgeType.BRAND.value),
            ("rules", KnowledgeType.RULE.value),
            ("examples", KnowledgeType.EXAMPLE.value),
            ("claims", KnowledgeType.CLAIM.value),
            ("preferences", KnowledgeType.PREFERENCE.value),
        ):
            if key in sections and label not in sources:
                sources.append(label)

        if knowledge_block_parts:
            sections["knowledge"] = "\n\n---\n\n".join(knowledge_block_parts)

        order = [
            "brand",
            "rules",
            "preferences",
            "examples",
            "claims",
            "planner",
            "knowledge",
        ]
        ordered_keys = [k for k in order if k in sections] + [
            k for k in sections if k not in order
        ]
        text_parts = [f"## {k.upper()}\n{sections[k]}" for k in ordered_keys]
        text = "\n\n".join(text_parts)
        estimate = self._budget.estimate(text)

        citation_map = CitationMap(entries=tuple(citation_entries))
        return OptimizedContext(
            text=text,
            citations=citation_map.as_dicts(),
            citation_map=citation_map,
            knowledge_sources=tuple(sources),
            items=knowledge_items,
            token_estimate=estimate,
            token_budget=budget,
            sections=sections,
            metrics={
                "section_count": len(sections),
                "knowledge_count": len(knowledge_items),
                "citation_count": len(citation_entries),
                "tokens_before_compress": inp.compressed.tokens_before,
                "tokens_after_compress": inp.compressed.tokens_after,
                "token_estimate": estimate,
            },
        )
