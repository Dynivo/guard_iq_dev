"""Typography asset ORM (M11)."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class TypographyAssetRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "typography_assets"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    image_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    svg_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    layers_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    layout_enrichment_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    typography_plan_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    brand_application_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    overlay_validation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    brand_validation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    slide_composition_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    typography_intelligence_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    design_tokens_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1080)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1350)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    accessibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    brand_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    typography_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    contrast_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TypographyTemplateRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "typography_templates"

    template_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False, default="1")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
