"""In-memory execution history store."""

from __future__ import annotations

from collections import defaultdict

from app.modules.workflow.domain.models import ExecutionHistoryRecord


class InMemoryExecutionHistoryStore:
    def __init__(self) -> None:
        self._records: dict[str, list[ExecutionHistoryRecord]] = defaultdict(list)

    async def append(self, record: ExecutionHistoryRecord) -> None:
        self._records[record.execution_id].append(record)

    async def list_for_execution(self, execution_id: str) -> list[ExecutionHistoryRecord]:
        return list(self._records.get(execution_id, []))
