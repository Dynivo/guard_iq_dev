"""Prompt Diff — structural/text comparison of two definitions."""

from __future__ import annotations

import difflib

from app.modules.prompts.domain.models import PromptDefinition, PromptDiff


class DefaultPromptDiffer:
    def diff(self, left: PromptDefinition, right: PromptDefinition) -> PromptDiff:
        left_text = _definition_text(left)
        right_text = _definition_text(right)
        if left_text == right_text:
            return PromptDiff(
                name=left.name,
                left_version=left.version,
                right_version=right.version,
                identical=True,
            )

        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        sm = difflib.SequenceMatcher(a=left_lines, b=right_lines)
        added: list[str] = []
        removed: list[str] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "delete":
                removed.extend(left_lines[i1:i2])
            elif tag == "insert":
                added.extend(right_lines[j1:j2])
            elif tag == "replace":
                removed.extend(left_lines[i1:i2])
                added.extend(right_lines[j1:j2])

        return PromptDiff(
            name=left.name,
            left_version=left.version,
            right_version=right.version,
            added_lines=tuple(added),
            removed_lines=tuple(removed),
            identical=False,
        )


def _definition_text(defn: PromptDefinition) -> str:
    parts = [f"# {defn.name}@{defn.version}", f"capability={defn.capability}"]
    if defn.template:
        parts.append(defn.template)
    for sec in sorted(defn.sections, key=lambda s: s.order):
        parts.append(f"## {sec.name}\n{sec.body}")
    return "\n".join(parts)
