"""Prompt Compiler — DSL render + section assembly + size estimate."""

from __future__ import annotations

from pathlib import Path

from app.modules.prompts.application.dsl import PromptDSL
from app.modules.prompts.domain.models import CompiledPrompt, PromptDefinition

# Stable section order for assembled prompts
SECTION_ORDER = (
    "system",
    "brand",
    "rules",
    "preferences",
    "examples",
    "claims",
    "knowledge",
    "planner",
    "task",
    "output_format",
    "validation",
)


class DefaultPromptCompiler:
    def __init__(self, partials_dir: Path | None = None) -> None:
        self._dsl = PromptDSL(partials_dir)

    def compile(
        self, definition: PromptDefinition, variables: dict[str, str]
    ) -> CompiledPrompt:
        sections: dict[str, str] = {}
        used: set[str] = set()

        if definition.sections:
            for sec in sorted(definition.sections, key=lambda s: s.order):
                rendered = self._dsl.render(sec.body, variables)
                if rendered.strip():
                    sections[sec.name] = rendered
                used.update(self._dsl.extract_variables(sec.body))
            # Fill standard section slots from variables when template sections omit them
            for key in SECTION_ORDER:
                if key not in sections and variables.get(key):
                    sections[key] = variables[key]
        else:
            body = self._dsl.render(definition.template or "", variables)
            sections["task"] = body
            used.update(self._dsl.extract_variables(definition.template or ""))
            for key in SECTION_ORDER:
                if key != "task" and variables.get(key):
                    sections[key] = variables[key]

        system = sections.pop("system", "") if "system" in sections else variables.get("system", "")
        ordered_keys = [k for k in SECTION_ORDER if k in sections and k != "system"]
        ordered_keys += [k for k in sections if k not in SECTION_ORDER and k != "system"]
        parts = []
        for key in ordered_keys:
            parts.append(f"## {key.upper()}\n{sections[key]}")
        text = "\n\n".join(parts).strip()
        if system:
            # system kept separate for Orchestrator.system_message
            pass
        estimate = max(1, len(text) // 4)
        return CompiledPrompt(
            text=text,
            system_message=system,
            sections={**sections, **({"system": system} if system else {})},
            token_estimate=estimate,
            variables_used=tuple(sorted(used)),
            prompt_id=definition.id,
            prompt_version=definition.version,
            capability=definition.capability,
            schema_id=definition.schema_id,
        )
