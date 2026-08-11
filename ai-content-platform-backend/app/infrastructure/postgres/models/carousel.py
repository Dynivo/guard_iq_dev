"""Carousel and media models: decks, slides, templates, assets, exports (M12 extended)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class CarouselDeck(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "carousel_decks"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    slide_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_deck_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    deck_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CarouselSlide(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "carousel_slides"

    deck_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("carousel_decks.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structured_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    rendered_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    svg_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    composition_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Template(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="carousel")
    html_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    preview_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    variables_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MediaAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "media_assets"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exif_stripped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Export(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "exports"

    deck_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("carousel_decks.id"), nullable=True, index=True
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    size: Mapped[str] = mapped_column(String(20), nullable=False, default="1080x1350")
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CarouselAssetRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "carousel_assets"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    deck_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deck_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rendered_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exports_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    typography_asset_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    image_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    render_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    export_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deck_definition_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dependency_graph_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    optimization_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    export_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)


class DeckVersionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "deck_versions"

    deck_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deck_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class RenderJobRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "render_jobs"

    deck_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1080)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1350)
    render_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ExportJobRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "export_jobs"

    deck_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    formats: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    export_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ExportArtifactRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "export_artifacts"

    deck_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    export_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
