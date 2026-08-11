"""In-memory Prompt Replay store."""

from __future__ import annotations

from app.modules.prompts.domain.models import PromptReplayRecord


class InMemoryPromptReplayStore:
    def __init__(self) -> None:
        self._by_id: dict[str, PromptReplayRecord] = {}

    async def save(self, record: PromptReplayRecord) -> None:
        self._by_id[record.replay_id] = record

    async def get(self, replay_id: str) -> PromptReplayRecord | None:
        return self._by_id.get(replay_id)

    def list_all(self) -> list[PromptReplayRecord]:
        return list(self._by_id.values())
