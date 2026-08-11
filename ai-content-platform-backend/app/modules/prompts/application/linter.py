"""Prompt Linter — unused/duplicate/unknown vars, invalid includes, cycles."""

from __future__ import annotations

from pathlib import Path

from app.modules.prompts.application.dsl import PromptDSL
from app.modules.prompts.domain.models import LintResult, PromptDefinition


class DefaultPromptLinter:
    def __init__(self, partials_dir: Path | None = None) -> None:
        self._partials_dir = partials_dir

    def lint(
        self,
        definition: PromptDefinition,
        *,
        partials_dir: Path | None = None,
    ) -> LintResult:
        pdir = partials_dir or self._partials_dir
        dsl = PromptDSL(pdir)
        errors: list[str] = []
        warnings: list[str] = []

        declared = [spec.name for spec in definition.variables]
        seen: set[str] = set()
        for name in declared:
            if name in seen:
                errors.append(f"duplicate variable: {name}")
            seen.add(name)

        bodies: list[str] = [definition.template or ""]
        bodies.extend(sec.body for sec in definition.sections)
        referenced: set[str] = set()
        for body in bodies:
            referenced.update(dsl.extract_variables(body))
            for e in dsl.validate_expression_syntax(body):
                errors.append(e)

        # Partials may introduce more vars
        graph: dict[str, str] = {"__root__": "\n".join(bodies)}
        if pdir and pdir.exists():
            for path in list(pdir.glob("*.md")) + list(pdir.glob("*.txt")):
                text = path.read_text(encoding="utf-8")
                graph[path.stem] = text
                referenced.update(dsl.extract_variables(text))

        for cycle in dsl.find_circular_includes(graph, entry="__root__"):
            errors.append(f"recursive template: {cycle}")

        for body in bodies:
            for inc in dsl.extract_includes(body):
                if pdir is None or dsl.resolve_partial_path(inc) is None:
                    # Allow include of known graph keys (section names not partials)
                    if inc not in graph:
                        errors.append(f"invalid include / missing partial: {inc}")

        declared_set = set(declared)
        # Built-in section vars often injected at runtime without being declared
        runtime_ok = {
            "knowledge",
            "brand",
            "rules",
            "examples",
            "claims",
            "preferences",
            "planner",
            "output_format",
            "schema_id",
            "system",
        }
        for name in sorted(referenced - declared_set - runtime_ok):
            warnings.append(f"unknown variable: {name}")

        for name in sorted(declared_set - referenced):
            warnings.append(f"unused variable: {name}")

        return LintResult(
            ok=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
