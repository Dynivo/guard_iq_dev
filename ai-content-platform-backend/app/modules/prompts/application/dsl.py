"""Lightweight Prompt DSL — variables, conditions, includes (no Jinja dependency)."""

from __future__ import annotations

import re
from pathlib import Path

_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_IF = re.compile(
    r"\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}(.*?)\{%\s*endif\s*%\}",
    re.DOTALL,
)
_INCLUDE = re.compile(r"\{%\s*include\s+['\"]([^'\"]+)['\"]\s*%\}")
_LEGACY_VAR = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_OPEN_IF = re.compile(r"\{%\s*if\s+")
_CLOSE_IF = re.compile(r"\{%\s*endif\s*%\}")


class PromptDSL:
    def __init__(self, partials_dir: Path | None = None) -> None:
        self._partials_dir = partials_dir

    def render(self, template: str, variables: dict[str, str]) -> str:
        text = self._resolve_includes(template)
        text = self._resolve_conditions(text, variables)
        text = self._substitute(text, variables)
        return text.strip()

    def extract_variables(self, template: str) -> set[str]:
        names = set(_VAR.findall(template))
        names.update(_LEGACY_VAR.findall(template))
        for m in _IF.finditer(template):
            names.add(m.group(1))
        return names

    def extract_includes(self, template: str) -> list[str]:
        return list(_INCLUDE.findall(template))

    def find_circular_includes(
        self, templates: dict[str, str], *, entry: str | None = None
    ) -> list[str]:
        """Return cycle descriptions found in the include graph."""
        cycles: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def walk(name: str, stack: list[str]) -> None:
            if name in visiting:
                idx = stack.index(name) if name in stack else 0
                cycles.append(" -> ".join(stack[idx:] + [name]))
                return
            if name in visited:
                return
            visiting.add(name)
            body = templates.get(name, "")
            for inc in self.extract_includes(body):
                walk(inc, stack + [name])
            visiting.remove(name)
            visited.add(name)

        roots = [entry] if entry else list(templates.keys())
        for root in roots:
            if root:
                walk(root, [])
        return cycles

    def validate_expression_syntax(self, template: str) -> list[str]:
        errors: list[str] = []
        opens = len(_OPEN_IF.findall(template))
        closes = len(_CLOSE_IF.findall(template))
        if opens != closes:
            errors.append(
                f"unmatched if/endif tags: {opens} if, {closes} endif"
            )
        if "{%" in template:
            leftovers = re.findall(r"\{%[^%]*%\}", template)
            for tag in leftovers:
                if re.match(r"\{%\s*if\s+%\}", tag):
                    errors.append("invalid if expression: missing variable")
                if re.match(r"\{%\s*include\s+%\}", tag) or re.match(
                    r"\{%\s*include\s*%\}", tag
                ):
                    errors.append("invalid include expression: missing name")
        return errors

    def resolve_partial_path(self, name: str) -> Path | None:
        if self._partials_dir is None:
            return None
        for ext in (".md", ".txt"):
            path = self._partials_dir / f"{name}{ext}"
            if path.exists():
                return path
        return None

    def _resolve_includes(
        self, template: str, depth: int = 0, stack: list[str] | None = None
    ) -> str:
        if depth > 8:
            return "<!-- include depth exceeded -->"
        stack = list(stack or [])

        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in stack:
                return f"<!-- circular include: {' -> '.join(stack + [name])} -->"
            if self._partials_dir is None:
                return ""
            path = self.resolve_partial_path(name)
            if path is None:
                return f"<!-- missing partial: {name} -->"
            return self._resolve_includes(
                path.read_text(encoding="utf-8"), depth + 1, stack + [name]
            )

        return _INCLUDE.sub(repl, template)

    def _resolve_conditions(self, template: str, variables: dict[str, str]) -> str:
        def repl(match: re.Match[str]) -> str:
            var = match.group(1)
            body = match.group(2)
            val = (variables.get(var) or "").strip()
            return body if val else ""

        prev = None
        text = template
        while prev != text:
            prev = text
            text = _IF.sub(repl, text)
        return text

    def _substitute(self, template: str, variables: dict[str, str]) -> str:
        def repl_mustache(match: re.Match[str]) -> str:
            key = match.group(1)
            return variables.get(key, "")

        text = _VAR.sub(repl_mustache, template)

        def repl_legacy(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in variables:
                return variables.get(key, "")
            return match.group(0)

        return _LEGACY_VAR.sub(repl_legacy, text)
