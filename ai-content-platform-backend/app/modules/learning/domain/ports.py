"""Learning module ports — capture, process, store, libraries."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.learning.domain.models import KnowledgeArtifact, LearningEvent, PreferenceUpdate
from app.shared.events.types import DomainEvent


class ExampleLibrary(Protocol):
    async def list_active(self, org_id: uuid.UUID) -> list[dict]: ...

    async def add(self, org_id: uuid.UUID, example: dict) -> uuid.UUID: ...

    async def deactivate(self, example_id: uuid.UUID) -> None: ...


class RulesLibrary(Protocol):
    async def list_active(self, org_id: uuid.UUID) -> list[dict]: ...

    async def add(self, org_id: uuid.UUID, rule: dict) -> uuid.UUID: ...

    async def deactivate(self, rule_id: uuid.UUID) -> None: ...


class PreferenceStore(Protocol):
    async def list_active(self, org_id: uuid.UUID) -> list[dict]: ...

    async def upsert(self, org_id: uuid.UUID, preference: dict) -> uuid.UUID: ...


class LearningCapturePort(Protocol):
    def capture(self, event: DomainEvent) -> LearningEvent: ...


class LearningProcessorPort(Protocol):
    def process(self, learning_event: LearningEvent) -> list[KnowledgeArtifact]: ...


class LearningStorePort(Protocol):
    async def store(
        self, artifacts: list[KnowledgeArtifact]
    ) -> list[dict]: ...

    async def record_preference_update(self, update: PreferenceUpdate) -> PreferenceUpdate: ...
