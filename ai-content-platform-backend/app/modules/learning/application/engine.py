"""LearningEngine — capture → process → store facade."""

from __future__ import annotations

from typing import Any

from app.modules.learning.application.capture import LearningCapture
from app.modules.learning.application.metrics import InMemoryLearningMetrics
from app.modules.learning.application.processor import LearningProcessor
from app.modules.learning.application.store import InMemoryLearningStore
from app.modules.learning.domain.models import KnowledgeArtifact, LearningEvent
from app.shared.events.types import DomainEvent


class LearningEngine:
    def __init__(
        self,
        *,
        capture: LearningCapture | None = None,
        processor: LearningProcessor | None = None,
        store: InMemoryLearningStore | None = None,
        metrics: InMemoryLearningMetrics | None = None,
        config_dir: str | None = None,
    ) -> None:
        self.capture = capture or LearningCapture(config_dir)
        self.processor = processor or LearningProcessor(config_dir)
        self.store = store or InMemoryLearningStore(config_dir)
        self.metrics = metrics or InMemoryLearningMetrics()

    def capture_event(self, event: DomainEvent) -> LearningEvent | None:
        le = self.capture.capture(event)
        if le is not None:
            self.store.events.append(le.to_dict())
            self.metrics.record_capture()
        return le

    def process_event(self, learning_event: LearningEvent) -> list[KnowledgeArtifact]:
        artifacts = self.processor.process(learning_event)
        self.metrics.record_process(len(artifacts))
        return artifacts

    async def store_artifacts(self, artifacts: list[KnowledgeArtifact]) -> list[dict[str, Any]]:
        stored = await self.store.store(artifacts)
        self.metrics.record_store(len(stored))
        return stored

    async def handle_domain_event(self, event: DomainEvent) -> dict[str, Any]:
        le = self.capture_event(event)
        if le is None:
            return {"captured": False}
        artifacts = self.process_event(le)
        stored = await self.store_artifacts(artifacts)
        return {
            "captured": True,
            "learning_event": le.to_dict(),
            "artifacts": [a.to_dict() for a in artifacts],
            "stored": stored,
            "status": self.store.status(),
        }
