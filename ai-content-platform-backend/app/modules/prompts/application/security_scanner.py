"""Prompt Security Scanner — injection, cycles, unsafe vars, invalid expressions."""

from __future__ import annotations

import re
from pathlib import Path

from app.modules.prompts.application.dsl import PromptDSL
from app.modules.prompts.domain.models import (
    CompiledPrompt,
    PromptDefinition,
    SecurityScanResult,
)

_INJECTION = re.compile(
    r"(ignore\s+previous\s+instructions|system\s*:\s*you\s+are|<\/?script>"
    r"|<\s*\|?\s*system\s*\|?\s*>|\{\{\s*system\s*\}\})",
    re.IGNORECASE,
)


class DefaultPromptSecurityScanner:
    def __init__(self, partials_dir: Path | None = None) -> None:
        self._partials_dir = partials_dir
        self._dsl = PromptDSL(partials_dir)

    def scan(
        self,
        definition: PromptDefinition,
        compiled: CompiledPrompt,
        variables: dict[str, str],
        *,
        partials_dir: Path | None = None,
    ) -> SecurityScanResult:
        dsl = PromptDSL(partials_dir or self._partials_dir)
        errors: list[str] = []

        bodies: dict[str, str] = {"__root__": definition.template or ""}
        for sec in definition.sections:
            bodies[f"section:{sec.name}"] = sec.body
            bodies["__root__"] += "\n" + sec.body

        # Load partials into graph
        pdir = partials_dir or self._partials_dir
        if pdir and pdir.exists():
            for path in list(pdir.glob("*.md")) + list(pdir.glob("*.txt")):
                bodies[path.stem] = path.read_text(encoding="utf-8")

        for cycle in dsl.find_circular_includes(bodies, entry="__root__"):
            errors.append(f"circular template include: {cycle}")

        # Also detect circular markers left by render
        blob = f"{compiled.system_message}\n{compiled.text}"
        if "circular include:" in blob or "include depth exceeded" in blob:
            errors.append("recursive or circular include detected in compiled prompt")

        for key, val in variables.items():
            if _INJECTION.search(val or ""):
                errors.append(f"prompt injection placeholder in variable: {key}")
            if _INJECTION.search(key):
                errors.append(f"unsafe variable name: {key}")

        for spec in definition.variables:
            if spec.required and not (variables.get(spec.name) or "").strip():
                errors.append(f"missing required variable: {spec.name}")

        for sec in definition.sections:
            errors.extend(
                f"invalid expression in section '{sec.name}': {e}"
                for e in dsl.validate_expression_syntax(sec.body)
            )
        if definition.template:
            errors.extend(
                f"invalid expression in template: {e}"
                for e in dsl.validate_expression_syntax(definition.template)
            )

        # Missing partials referenced
        for name, body in bodies.items():
            for inc in dsl.extract_includes(body):
                if pdir and dsl.resolve_partial_path(inc) is None and inc not in bodies:
                    errors.append(f"missing partial include: {inc}")

        return SecurityScanResult(safe=len(errors) == 0, errors=tuple(errors))
