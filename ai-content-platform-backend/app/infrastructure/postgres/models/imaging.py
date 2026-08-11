"""ImageJob ORM — M10 enrichment columns."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ImageJob(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "image_jobs"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    visual_plan_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prompt_enhanced: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # M10 additive
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workflow_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scene_plan_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    composition_plan_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    policy_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prompt_request_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    queue_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    replay_of_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # M10r additive
    layout_plan_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    asset_intelligence_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_breakdown_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brief_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    replay_record_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ImageJobArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "image_job_artifacts"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("image_jobs.id"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ImageWorkflowRegistryEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit mirror of file-backed Comfy workflow registry."""

    __tablename__ = "image_workflow_registry"

    workflow_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="comfyui")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    graph_path: Mapped[str] = mapped_column(String(512), nullable=False)
    parameters_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
