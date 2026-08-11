"""Background job tracking models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    payload_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class JobEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_events"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
