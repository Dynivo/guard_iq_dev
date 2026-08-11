"""Workflow engine persistence models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.postgres.session import Base


class WorkflowExecutionEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only workflow lifecycle / node events for execution history."""

    __tablename__ = "workflow_execution_events"

    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
