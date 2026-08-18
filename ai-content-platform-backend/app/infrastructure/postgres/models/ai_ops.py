"""AI operations models: prompt versions, LLM calls, provider configs."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class PromptVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_versions"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variables_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    examples_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    eval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    approval_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="approved"
    )
    capability: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    schema_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sections_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PromptGoldenCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_golden_cases"

    case_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expected_contains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    expected_json_keys: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptEvalRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_eval_runs"

    prompt_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    suite_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    results_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PromptReplay(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_replay"

    replay_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    prompt_id: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    capability: Mapped[str] = mapped_column(String(100), nullable=False)
    compiled_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compiled_text: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class LlmCall(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "llm_calls"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProviderConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "provider_configs"

    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ProviderBudget(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    """Current-month hard spending ceiling shared by every model at a provider."""

    __tablename__ = "provider_budgets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provider", name="uq_provider_budgets_org_provider"
        ),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    monthly_limit_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("10.000000")
    )
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0.000000")
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProviderBudgetReservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Short-lived reservation preventing concurrent calls from overspending."""

    __tablename__ = "provider_budget_reservations"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("provider_budgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
