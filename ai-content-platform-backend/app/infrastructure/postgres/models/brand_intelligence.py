"""ORM models for Brand Intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BrandProfileRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_profiles"

    kind: Mapped[str] = mapped_column(String(40), nullable=False, server_default="corporate")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    active_memory_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class BrandPersonaRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_personas"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    voice_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))


class NeverSayPolicyRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_never_say_policies"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    forbidden: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    discouraged: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    legal_restrictions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    compliance_restrictions: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'[]'::jsonb")
    )
    avoid_vocabulary: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    never_use: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    preferred_alternatives: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )


class BrandImportRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_imports"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="pending")
    source_mix_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    watermark_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class BrandImportJobRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_import_jobs"

    import_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, server_default="pending")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    eta_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CanonicalBrandObjectRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "canonical_brand_objects"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_imports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, server_default="", index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    media_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    engagement: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))


class BrandMemoryRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_memories"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lifecycle: Mapped[str] = mapped_column(String(40), nullable=False, server_default="draft")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    brand_dna_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    writing_dna_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    visual_dna_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    engagement_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    completeness_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )
    health_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    recommendations_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'[]'::jsonb")
    )


class BrandMemoryVersionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_memory_versions"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_memories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class BrandMemoryReviewRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_memory_reviews"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_memories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="open")
    detections_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )
    edits_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))


class LogoAssetSetRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_logo_asset_sets"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    variants_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    primary_key: Mapped[str | None] = mapped_column(String(500), nullable=True)


class BrandBrowserSessionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_browser_sessions"

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BrandVectorChunkRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "brand_vector_chunks"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    memory_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(80), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
