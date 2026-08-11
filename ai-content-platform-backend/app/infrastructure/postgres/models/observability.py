"""Observability ORM models — AI/workflow traces, evaluations, metrics, cost."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class AITraceRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "ai_traces"

    request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    capability: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    event_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowTraceRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "workflow_traces"

    execution_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_name: Mapped[str] = mapped_column(String(150), nullable=False)
    node_id: Mapped[str] = mapped_column(String(150), nullable=False)
    phase: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dependencies_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvaluationResultRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "evaluation_results"

    evaluation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(150), nullable=False)
    scores_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    overall: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    signals_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    inputs_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ProviderMetricsRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "provider_metrics"

    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeouts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fallbacks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_classes_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ModelMetricsRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "model_metrics"

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approval_score_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approval_score_n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hallucination_reports: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_score_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality_score_n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CostRecordRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "cost_records"

    category: Mapped[str] = mapped_column(String(40), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class OrganizationUsageRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "organization_usage"

    period: Mapped[str] = mapped_column(String(20), nullable=False)  # daily | monthly
    period_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    usage_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class WorkflowStatisticsRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "workflow_statistics"

    workflow_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
