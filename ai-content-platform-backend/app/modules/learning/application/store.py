"""LearningStore — versioned persistence; never overwrite without history."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.learning import (
    Example,
    KnowledgeSignalRow,
    Rule,
    WritingPreference,
)
from app.modules.learning.application.config_loader import load_learning_config
from app.modules.learning.application.lifecycle import KnowledgeLifecycleService
from app.modules.learning.domain.models import (
    KnowledgeArtifact,
    KnowledgeLifecycle,
    LearningArtifactKind,
    PreferenceUpdate,
)


def _confidence_kwargs(art: KnowledgeArtifact) -> dict[str, Any]:
    return {
        "confidence": art.confidence,
        "approval_count": art.approval_count,
        "usage_count": art.usage_count,
        "success_rate": art.success_rate,
        "created_from_review": art.created_from_review,
        "last_used": art.last_used,
        "lifecycle": str(art.lifecycle),
        "is_active": art.is_active,
    }


class InMemoryLearningStore:
    """History-preserving in-memory store for unit tests and workflow nodes."""

    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_learning_config(config_dir)
        self._lifecycle = KnowledgeLifecycleService(config_dir)
        self.events: list[dict[str, Any]] = []
        self.examples: list[dict[str, Any]] = []
        self.rules: list[dict[str, Any]] = []
        self.preferences: list[dict[str, Any]] = []
        self.signals: list[dict[str, Any]] = []
        self.recommendations: list[dict[str, Any]] = []
        self.preference_updates: list[PreferenceUpdate] = []

    def _store_cfg(self) -> dict[str, Any]:
        return (self._config.get("store") or {}).get("store") or {}

    async def store(self, artifacts: list[KnowledgeArtifact]) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        for art in artifacts:
            if art.created_from_review:
                art.lifecycle = KnowledgeLifecycle.APPROVED
            elif art.lifecycle != KnowledgeLifecycle.CANDIDATE:
                art.lifecycle = KnowledgeLifecycle.CANDIDATE
            row = art.to_dict()
            row["id"] = str(uuid.uuid4())
            row["stored_at"] = datetime.now(timezone.utc).isoformat()
            row["is_active"] = self._lifecycle.is_active_flag(art.lifecycle)
            if art.kind == LearningArtifactKind.EXAMPLE:
                self.examples.append(row)
            elif art.kind == LearningArtifactKind.NEGATIVE_RULE:
                self.rules.append(row)
            elif art.kind == LearningArtifactKind.WRITING_PREFERENCE:
                await self._store_preference(art, row)
            elif art.kind == LearningArtifactKind.BRAND_PREFERENCE:
                await self._store_preference(art, row)
            elif art.kind == LearningArtifactKind.KNOWLEDGE_SIGNAL:
                self.signals.append(row)
            elif art.kind == LearningArtifactKind.RECOMMENDATION:
                self.recommendations.append(row)
            stored.append(row)
        return stored

    async def _store_preference(self, art: KnowledgeArtifact, row: dict[str, Any]) -> None:
        cfg = self._store_cfg()
        previous = None
        prev_id = None
        same = [
            p
            for p in self.preferences
            if p.get("organization_id") == str(art.organization_id)
            and p.get("category") == art.category
            and p.get("lifecycle") != KnowledgeLifecycle.ARCHIVED
        ]
        if same and cfg.get("never_overwrite_in_place", True):
            previous = same[-1]
            prev_id = previous.get("id")
            if cfg.get("deactivate_superseded", True):
                previous["is_active"] = False
                if previous.get("lifecycle") == KnowledgeLifecycle.APPROVED:
                    previous["lifecycle"] = KnowledgeLifecycle.DEPRECATED
            row["version"] = int(previous.get("version") or 1) + 1
            row["supersedes_id"] = prev_id
            update = PreferenceUpdate(
                id=uuid.uuid4(),
                organization_id=art.organization_id,
                preference_id=uuid.UUID(str(prev_id)) if prev_id else None,
                previous_text=previous.get("body"),
                new_text=art.body,
                category=art.category,
                source_learning_event_id=art.source_learning_event_id,
                created_at=datetime.now(timezone.utc),
            )
            self.preference_updates.append(update)
        row["lifecycle"] = str(art.lifecycle)
        row["is_active"] = self._lifecycle.is_active_flag(art.lifecycle)
        self.preferences.append(row)

    async def transition_lifecycle(
        self, collection: str, artifact_id: str, target: str
    ) -> dict[str, Any]:
        from app.shared.result import Failure

        bags = {
            "examples": self.examples,
            "rules": self.rules,
            "preferences": self.preferences,
            "signals": self.signals,
        }
        items = bags.get(collection) or []
        for item in items:
            if item.get("id") == artifact_id:
                result = self._lifecycle.transition(item.get("lifecycle") or "candidate", target)
                if isinstance(result, Failure):
                    raise ValueError(result.message)
                item["lifecycle"] = result.value["lifecycle"]
                item["is_active"] = result.value["is_active"]
                return item
        raise KeyError(artifact_id)

    async def record_preference_update(self, update: PreferenceUpdate) -> PreferenceUpdate:
        self.preference_updates.append(update)
        return update

    def status(self) -> dict[str, Any]:
        def _by_life(items: list[dict[str, Any]]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for i in items:
                key = str(i.get("lifecycle") or "candidate")
                counts[key] = counts.get(key, 0) + 1
            return counts

        return {
            "examples": len(self.examples),
            "rules": len(self.rules),
            "preferences": len(self.preferences),
            "preferences_active": len(
                [p for p in self.preferences if p.get("is_active")]
            ),
            "signals": len(self.signals),
            "recommendations": len(self.recommendations),
            "preference_updates": len(self.preference_updates),
            "events": len(self.events),
            "lifecycle": {
                "examples": _by_life(self.examples),
                "rules": _by_life(self.rules),
                "preferences": _by_life(self.preferences),
                "signals": _by_life(self.signals),
            },
        }


class SessionLearningStore:
    """Persist examples/rules/preferences/signals via SQLAlchemy."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        config_dir: str | None = None,
        preference_updates: list[PreferenceUpdate] | None = None,
        learning_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self._session = session
        self._config = load_learning_config(config_dir)
        self._lifecycle = KnowledgeLifecycleService(config_dir)
        self.preference_updates = preference_updates if preference_updates is not None else []
        self.learning_events = learning_events if learning_events is not None else []

    async def store(self, artifacts: list[KnowledgeArtifact]) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        for art in artifacts:
            # Review approve/reject already validated the draft — activate immediately.
            if art.created_from_review:
                art.lifecycle = KnowledgeLifecycle.APPROVED
            elif art.lifecycle != KnowledgeLifecycle.CANDIDATE:
                art.lifecycle = KnowledgeLifecycle.CANDIDATE
            conf = _confidence_kwargs(art)
            if art.kind == LearningArtifactKind.EXAMPLE:
                meta = art.metadata or {}
                draft_raw = meta.get("draft_id")
                row = Example(
                    organization_id=art.organization_id,
                    draft_id=uuid.UUID(str(draft_raw)) if draft_raw else None,
                    content_type=str(meta.get("content_type") or art.category),
                    text=art.body,
                    hook=meta.get("hook"),
                    tags_json=list(meta.get("tags") or ["approved"]),
                    weight=float(meta.get("weight") or 1.0),
                    version=art.version,
                    supersedes_id=art.supersedes_id,
                    **conf,
                )
                self._session.add(row)
                await self._session.flush()
                stored.append({"id": str(row.id), "kind": str(art.kind), **conf})
            elif art.kind == LearningArtifactKind.NEGATIVE_RULE:
                meta = art.metadata or {}
                fb = meta.get("feedback_event_id")
                row = Rule(
                    organization_id=art.organization_id,
                    category=art.category,
                    text=art.body,
                    source_feedback_id=uuid.UUID(str(fb)) if fb else None,
                    priority=int(meta.get("priority") or 10),
                    version=art.version,
                    supersedes_id=art.supersedes_id,
                    **conf,
                )
                self._session.add(row)
                await self._session.flush()
                stored.append({"id": str(row.id), "kind": str(art.kind), **conf})
            elif art.kind in {
                LearningArtifactKind.WRITING_PREFERENCE,
                LearningArtifactKind.BRAND_PREFERENCE,
            }:
                meta = art.metadata or {}
                row = WritingPreference(
                    organization_id=art.organization_id,
                    category=art.category,
                    preference=art.body,
                    source_type=str(meta.get("source_type") or "learning"),
                    version=art.version,
                    supersedes_id=art.supersedes_id,
                    **conf,
                )
                self._session.add(row)
                await self._session.flush()
                update = PreferenceUpdate(
                    id=uuid.uuid4(),
                    organization_id=art.organization_id,
                    preference_id=row.id,
                    previous_text=None,
                    new_text=art.body,
                    category=art.category,
                    source_learning_event_id=art.source_learning_event_id,
                    created_at=datetime.now(timezone.utc),
                )
                self.preference_updates.append(update)
                stored.append({"id": str(row.id), "kind": str(art.kind), **conf})
            elif art.kind == LearningArtifactKind.KNOWLEDGE_SIGNAL:
                meta = art.metadata or {}
                row = KnowledgeSignalRow(
                    organization_id=art.organization_id,
                    category=art.category,
                    body=art.body,
                    signal_type=str(meta.get("signal") or "generic"),
                    metadata_json=dict(meta),
                    version=art.version,
                    supersedes_id=art.supersedes_id,
                    **conf,
                )
                self._session.add(row)
                await self._session.flush()
                stored.append({"id": str(row.id), "kind": str(art.kind), **conf})
            else:
                stored.append(
                    {
                        "id": str(uuid.uuid4()),
                        "kind": str(art.kind),
                        "body": art.body,
                        **conf,
                    }
                )
        return stored

    async def record_preference_update(self, update: PreferenceUpdate) -> PreferenceUpdate:
        self.preference_updates.append(update)
        return update
