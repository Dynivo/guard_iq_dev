"""Capture intake sessions and uploaded assets (voice / photos)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.postgres.session import Base


class CaptureSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "capture_sessions"

    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    photo_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="intake")
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_questions_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    follow_up_answers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    shot_list_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=True, index=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CaptureAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "capture_assets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # audio | photo
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
