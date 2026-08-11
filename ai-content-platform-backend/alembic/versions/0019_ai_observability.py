"""M14 AI Observability — additive trace/eval/cost/metrics tables.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_cols():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "ai_traces",
        *_base_cols(),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("workflow_id", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("capability", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_traces_request_id", "ai_traces", ["request_id"])
    op.create_index("ix_ai_traces_correlation_id", "ai_traces", ["correlation_id"])

    op.create_table(
        "workflow_traces",
        *_base_cols(),
        sa.Column("execution_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("workflow_name", sa.String(length=150), nullable=False),
        sa.Column("node_id", sa.String(length=150), nullable=False),
        sa.Column("phase", sa.String(length=40), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dependencies_json", JSONB(), nullable=True),
        sa.Column("outcome", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_traces_execution_id", "workflow_traces", ["execution_id"])
    op.create_index("ix_workflow_traces_correlation_id", "workflow_traces", ["correlation_id"])

    op.create_table(
        "evaluation_results",
        *_base_cols(),
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=150), nullable=False),
        sa.Column("scores_json", JSONB(), nullable=True),
        sa.Column("overall", sa.Float(), nullable=False, server_default="0"),
        sa.Column("signals_json", JSONB(), nullable=True),
        sa.Column("inputs_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_evaluation_results_evaluation_id", "evaluation_results", ["evaluation_id"])
    op.create_index("ix_evaluation_results_correlation_id", "evaluation_results", ["correlation_id"])

    op.create_table(
        "provider_metrics",
        *_base_cols(),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeouts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallbacks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_classes_json", JSONB(), nullable=True),
    )
    op.create_index("ix_provider_metrics_provider", "provider_metrics", ["provider"])

    op.create_table(
        "model_metrics",
        *_base_cols(),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cache_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approval_score_sum", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approval_score_n", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hallucination_reports", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_score_sum", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score_n", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_model_metrics_model", "model_metrics", ["model"])

    op.create_table(
        "cost_records",
        *_base_cols(),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("amount_usd", sa.Float(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("workflow_name", sa.String(length=150), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_cost_records_correlation_id", "cost_records", ["correlation_id"])

    op.create_table(
        "organization_usage",
        *_base_cols(),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("period_key", sa.String(length=40), nullable=False),
        sa.Column("usage_json", JSONB(), nullable=True),
        sa.Column("total_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_organization_usage_period_key", "organization_usage", ["period_key"])

    op.create_table(
        "workflow_statistics",
        *_base_cols(),
        sa.Column("workflow_name", sa.String(length=150), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_workflow_statistics_workflow_name", "workflow_statistics", ["workflow_name"]
    )


def downgrade() -> None:
    for table in (
        "workflow_statistics",
        "organization_usage",
        "cost_records",
        "model_metrics",
        "provider_metrics",
        "evaluation_results",
        "workflow_traces",
        "ai_traces",
    ):
        op.drop_table(table)
