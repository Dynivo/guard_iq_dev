"""Prompt Optimizer — dedupe, reorder, trim to token budget."""

from __future__ import annotations

from app.modules.prompts.application.compiler import SECTION_ORDER
from app.modules.prompts.domain.models import CompiledPrompt


class DefaultPromptOptimizer:
    def optimize(
        self, compiled: CompiledPrompt, *, token_budget: int
    ) -> CompiledPrompt:
        sections = dict(compiled.sections)
        # Drop empty / duplicate content
        seen: set[str] = set()
        cleaned: dict[str, str] = {}
        for key, val in sections.items():
            norm = " ".join(val.split()).lower()
            if not norm:
                continue
            digest = norm[:200]
            if digest in seen:
                continue
            seen.add(digest)
            cleaned[key] = val.strip()

        system = cleaned.pop("system", compiled.system_message)
        # Priority drop order when over budget (keep task/planner/system)
        drop_order = [
            "claims",
            "examples",
            "preferences",
            "knowledge",
            "brand",
            "rules",
            "validation",
        ]
        text = _assemble(system, cleaned)
        estimate = max(1, len(text) // 4)
        while estimate > token_budget and drop_order:
            victim = drop_order.pop(0)
            if victim in cleaned:
                cleaned.pop(victim)
                text = _assemble(system, cleaned)
                estimate = max(1, len(text) // 4)

        # Truncate task if still over
        if estimate > token_budget and "task" in cleaned:
            keep_chars = max(200, token_budget * 4 - 500)
            cleaned["task"] = cleaned["task"][:keep_chars]
            text = _assemble(system, cleaned)
            estimate = max(1, len(text) // 4)

        return CompiledPrompt(
            text=text,
            system_message=system,
            sections={**cleaned, **({"system": system} if system else {})},
            token_estimate=estimate,
            variables_used=compiled.variables_used,
            prompt_id=compiled.prompt_id,
            prompt_version=compiled.prompt_version,
            capability=compiled.capability,
            schema_id=compiled.schema_id,
        )


def _assemble(system: str, sections: dict[str, str]) -> str:
    ordered = [k for k in SECTION_ORDER if k in sections and k != "system"]
    ordered += [k for k in sections if k not in SECTION_ORDER and k != "system"]
    parts = [f"## {k.upper()}\n{sections[k]}" for k in ordered]
    return "\n\n".join(parts).strip()
