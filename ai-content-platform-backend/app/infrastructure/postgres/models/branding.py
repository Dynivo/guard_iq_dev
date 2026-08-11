"""Brand kit model for org-scoped brand configuration."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class BrandKit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "brand_kits"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#003366")
    secondary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#FFFFFF")
    accent_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    font_heading: Mapped[str] = mapped_column(String(100), nullable=False, default="Inter")
    font_body: Mapped[str] = mapped_column(String(100), nullable=False, default="Inter")
    logo_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tone_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    services_line: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_profile_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_profile_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
