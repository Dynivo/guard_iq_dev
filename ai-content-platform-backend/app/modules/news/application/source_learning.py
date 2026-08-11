"""Source learning — reputation improves from approvals/rejections/edits/engagement."""

from __future__ import annotations

from app.modules.news.application.reputation import DefaultSourceReputationEngine
from app.modules.news.domain.models import (
    SourceDefinition,
    SourceFeedbackEvent,
)


class InMemorySourceLearningStore:
    def __init__(self) -> None:
        self._events: list[SourceFeedbackEvent] = []
        self._sources: dict[str, SourceDefinition] = {}

    def record(self, event: SourceFeedbackEvent) -> None:
        self._events.append(event)

    def list_events(self, source_id: str) -> list[SourceFeedbackEvent]:
        return [e for e in self._events if e.source_id == source_id]

    def upsert_source(self, source: SourceDefinition) -> None:
        self._sources[source.source_id] = source

    def get_source(self, source_id: str) -> SourceDefinition | None:
        return self._sources.get(source_id)


class SourceLearningEngine:
    """Persist feedback and update authority/reliability/trust via reputation EMA."""

    def __init__(
        self,
        store: InMemorySourceLearningStore | None = None,
        *,
        alpha: float = 0.15,
        reputation: DefaultSourceReputationEngine | None = None,
    ) -> None:
        self._store = store or InMemorySourceLearningStore()
        self._alpha = alpha
        self._reputation = reputation or DefaultSourceReputationEngine()

    @property
    def store(self) -> InMemorySourceLearningStore:
        return self._store

    def apply(
        self, source: SourceDefinition, event: SourceFeedbackEvent
    ) -> SourceDefinition:
        self._store.record(event)
        updated = self._reputation.apply_feedback(
            source, event.kind, weight=event.weight, alpha=self._alpha
        )
        self._store.upsert_source(updated)
        return updated

    def reputation(self, source: SourceDefinition) -> dict[str, float]:
        return self._reputation.reputation(source)
