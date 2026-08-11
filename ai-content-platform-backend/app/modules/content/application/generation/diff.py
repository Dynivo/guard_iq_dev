"""Draft field-level diff."""

from __future__ import annotations

from app.modules.content.domain.models import DraftDiff, StructuredDraft

_FIELDS = ("hook", "body", "cta", "hashtags", "format", "content_type", "markdown")


class DefaultDraftDiffService:
    def diff(
        self,
        left: StructuredDraft,
        right: StructuredDraft,
        *,
        left_v: int = 1,
        right_v: int = 2,
    ) -> DraftDiff:
        changes: list[dict] = []
        ld = left.to_dict()
        rd = right.to_dict()
        for field in _FIELDS:
            if ld.get(field) != rd.get(field):
                changes.append(
                    {"field": field, "left": ld.get(field), "right": rd.get(field)}
                )
        return DraftDiff(
            left_version=left_v, right_version=right_v, changes=tuple(changes)
        )
