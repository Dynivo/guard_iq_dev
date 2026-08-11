"""AI request lifecycle tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AIRequestState(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    FALLBACK = "fallback"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AIRequestRecord:
    request_id: str
    correlation_id: str
    capability: str
    state: AIRequestState = AIRequestState.CREATED
    organization_id: uuid.UUID | None = None
    provider: str = ""
    model: str = ""
    prompt_hash: str = ""
    output_hash: str = ""
    cache_hit: bool = False
    latency_ms: int = 0
    cost_estimate: float = 0.0
    evaluation_status: str = "pending"
    error_message: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def transition(self, state: AIRequestState, *, detail: str = "") -> None:
        self.state = state
        self.updated_at = datetime.now(timezone.utc)
        self.history.append(
            {
                "state": state.value,
                "at": self.updated_at.isoformat(),
                "detail": detail,
            }
        )


class InMemoryLifecycleStore:
    def __init__(self) -> None:
        self._records: dict[str, AIRequestRecord] = {}

    async def save(self, record: AIRequestRecord) -> None:
        self._records[record.request_id] = record

    async def get(self, request_id: str) -> AIRequestRecord | None:
        return self._records.get(request_id)


class InMemoryRequestRecorder:
    """Records prompt/output hashes and call metadata for future replay."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    async def record(self, payload: dict[str, Any]) -> None:
        self._rows.append(dict(payload))

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)
