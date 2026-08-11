"""Generation replay store (in-memory for CI)."""

from __future__ import annotations

from app.modules.content.domain.models import GenerationReplayRecord


class InMemoryGenerationReplayStore:
    def __init__(self) -> None:
        self._rows: dict[str, GenerationReplayRecord] = {}

    def save(self, record: GenerationReplayRecord) -> None:
        self._rows[record.replay_id] = record

    def get(self, replay_id: str) -> GenerationReplayRecord | None:
        return self._rows.get(replay_id)

    def all(self) -> list[GenerationReplayRecord]:
        return list(self._rows.values())
