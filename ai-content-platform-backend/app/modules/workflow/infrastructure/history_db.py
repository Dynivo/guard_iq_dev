"""Null and PostgreSQL execution history adapters."""

from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.workflow import WorkflowExecutionEvent
from app.modules.workflow.domain.models import ExecutionHistoryRecord


class NullExecutionHistoryStore:
    """No-op history — useful when persistence is intentionally disabled."""

    async def append(self, record: ExecutionHistoryRecord) -> None:
        return None

    async def list_for_execution(self, execution_id: str) -> list[ExecutionHistoryRecord]:
        return []


class DatabaseExecutionHistoryStore:
    """Port-compliant async SQLAlchemy adapter for workflow execution events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, record: ExecutionHistoryRecord) -> None:
        row = WorkflowExecutionEvent(
            execution_id=record.execution_id,
            event=record.event,
            node_id=record.node_id,
            detail_json=dict(record.detail or {}),
            occurred_at=record.timestamp
            if record.timestamp.tzinfo
            else record.timestamp.replace(tzinfo=timezone.utc),
        )
        self._session.add(row)
        await self._session.flush()

    async def list_for_execution(self, execution_id: str) -> list[ExecutionHistoryRecord]:
        rows = (
            (
                await self._session.execute(
                    select(WorkflowExecutionEvent)
                    .where(WorkflowExecutionEvent.execution_id == execution_id)
                    .order_by(WorkflowExecutionEvent.occurred_at.asc())
                )
            )
            .scalars()
            .all()
        )
        return [
            ExecutionHistoryRecord(
                execution_id=r.execution_id,
                event=r.event,
                timestamp=r.occurred_at,
                node_id=r.node_id,
                detail=dict(r.detail_json or {}),
            )
            for r in rows
        ]
