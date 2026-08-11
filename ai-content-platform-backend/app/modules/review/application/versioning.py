"""Versioning — original / edited / approved / published + diff + rollback refs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.modules.review.domain.models import ReviewSession, ReviewVersionRef


class VersioningService:
    def record(
        self,
        session: ReviewSession,
        kind: str,
        *,
        text: str | None = None,
        version_id: str | None = None,
    ) -> ReviewSession:
        ref = ReviewVersionRef(
            kind=kind,
            text=text,
            draft_id=str(session.draft_id),
            version_id=version_id or str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.version_refs = tuple([*session.version_refs, ref])
        return session

    def diff(self, original: str, edited: str) -> dict[str, Any]:
        o = original or ""
        e = edited or ""
        # Simple edit-distance proxy (Levenshtein-lite via length + common prefix/suffix)
        prefix = 0
        while prefix < len(o) and prefix < len(e) and o[prefix] == e[prefix]:
            prefix += 1
        suffix = 0
        while (
            suffix < (len(o) - prefix)
            and suffix < (len(e) - prefix)
            and o[-(suffix + 1)] == e[-(suffix + 1)]
        ):
            suffix += 1
        changed_o = len(o) - prefix - suffix
        changed_e = len(e) - prefix - suffix
        distance = max(changed_o, changed_e) + abs(changed_o - changed_e)
        ratio = distance / max(len(o), len(e), 1)
        return {
            "original_len": len(o),
            "edited_len": len(e),
            "edit_distance": distance,
            "edit_ratio": round(ratio, 4),
            "common_prefix": prefix,
            "common_suffix": suffix,
        }

    def rollback_ref(self, session: ReviewSession, kind: str) -> ReviewVersionRef | None:
        for ref in reversed(session.version_refs):
            if ref.kind == kind:
                return ref
        return None
