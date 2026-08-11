"""Consensus Engine ORM models (M17 / ADR 0058)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.postgres.session import Base


class ConsensusRunRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_runs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False, default="")
    capability: Mapped[str] = mapped_column(String(100), nullable=False, default="writing")
    policy_id: Mapped[str] = mapped_column(String(80), nullable=False, default="balanced")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    final_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    panel_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusCandidateRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_candidates"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sections_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusEvaluationScoreRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_evaluation_scores"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False)
    composite: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scores_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusJudgeDecisionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_judge_decisions"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    rankings_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusMergeDecisionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_merge_decisions"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    strategy: Mapped[str] = mapped_column(String(80), nullable=False, default="section_best")
    merged_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    section_sources_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    merged_sections_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusMetricsRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_metrics"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    agreement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consensus_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ProviderWeightRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provider_weights"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reliability: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    latency: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    historical_success: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    domain_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    brand_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    writing_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    research_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    image_prompt_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusHistoricalQualityRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_historical_quality"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusCostHistoryRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_cost_history"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    panel_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ConsensusReplayRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consensus_replays"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
