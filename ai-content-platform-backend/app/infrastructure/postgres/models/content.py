"""Content pipeline models: plans, drafts, versions, variations, prompt history."""

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


class ContentPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "content_plans"

    article_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)


class Draft(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "drafts"

    article_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    content_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("content_plans.id"), nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    generated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cta: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hashtags_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lifecycle_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    draft_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_breakdown_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    visual_brief_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    safety_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    draft_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class DraftVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "draft_versions"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    draft_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class DraftVariation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "draft_variations"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=False, index=True
    )
    variation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PromptHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "prompt_history"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=True, index=True
    )
    prompt_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)


class GenerationReplay(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generation_replays"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=True, index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    prompt_request_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)