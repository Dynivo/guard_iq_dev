"""Draft lifecycle + in-memory version store."""

from __future__ import annotations

from dataclasses import replace

from app.modules.content.domain.models import (
    DraftLifecycleStatus,
    DraftVersionSnapshot,
    StructuredDraft,
)


class InMemoryDraftLifecycleStore:
    def __init__(self) -> None:
        self._versions: dict[str, list[DraftVersionSnapshot]] = {}
        self._current: dict[str, StructuredDraft] = {}

    def transition(self, draft: StructuredDraft, status: str) -> StructuredDraft:
        updated = replace(draft, lifecycle_status=status)
        key = draft.content_plan_id or draft.metadata.get("draft_id") or "anon"
        self._current[str(key)] = updated
        return updated

    def save_version(self, snapshot: DraftVersionSnapshot) -> None:
        self._versions.setdefault(snapshot.draft_id, []).append(snapshot)

    def list_versions(self, draft_id: str) -> list[DraftVersionSnapshot]:
        return list(self._versions.get(draft_id, []))

    def get_current(self, draft_id: str) -> StructuredDraft | None:
        return self._current.get(draft_id)
