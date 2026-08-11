"""M17 Multi-LLM Consensus Engine — additive persistence tables.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "consensus_runs",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("policy_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("final_text", sa.Text(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("panel_json", JSONB(), nullable=True),
        sa.Column("report_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_consensus_runs_run_id", "consensus_runs", ["run_id"], unique=True)
    op.create_index("ix_consensus_runs_correlation_id", "consensus_runs", ["correlation_id"])
    op.create_index("ix_consensus_runs_organization_id", "consensus_runs", ["organization_id"])

    op.create_table(
        "consensus_candidates",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("candidate_id", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_estimate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sections_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_consensus_candidates_run_id", "consensus_candidates", ["run_id"])

    op.create_table(
        "consensus_evaluation_scores",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("candidate_id", sa.String(length=80), nullable=False),
        sa.Column("composite", sa.Float(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("scores_json", JSONB(), nullable=True),
        sa.Column("details_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_consensus_evaluation_scores_run_id", "consensus_evaluation_scores", ["run_id"]
    )

    op.create_table(
        "consensus_judge_decisions",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("rankings_json", JSONB(), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_consensus_judge_decisions_run_id", "consensus_judge_decisions", ["run_id"]
    )

    op.create_table(
        "consensus_merge_decisions",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("strategy", sa.String(length=80), nullable=False),
        sa.Column("merged_text", sa.Text(), nullable=False),
        sa.Column("section_sources_json", JSONB(), nullable=True),
        sa.Column("merged_sections_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_consensus_merge_decisions_run_id", "consensus_merge_decisions", ["run_id"]
    )

    op.create_table(
        "consensus_metrics",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("agreement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consensus_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_json", JSONB(), nullable=True),
    )
    op.create_index("ix_consensus_metrics_run_id", "consensus_metrics", ["run_id"])

    op.create_table(
        "provider_weights",
        *_base(),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("reliability", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("latency", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("historical_success", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("domain_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("brand_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("writing_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("research_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("image_prompt_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_provider_weights_provider", "provider_weights", ["provider"])

    op.create_table(
        "consensus_historical_quality",
        *_base(),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("run_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_consensus_historical_quality_provider",
        "consensus_historical_quality",
        ["provider"],
    )

    op.create_table(
        "consensus_cost_history",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("panel_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("policy_id", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_consensus_cost_history_run_id", "consensus_cost_history", ["run_id"])

    op.create_table(
        "consensus_replays",
        *_base(),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("snapshot_json", JSONB(), nullable=True),
    )
    op.create_index("ix_consensus_replays_run_id", "consensus_replays", ["run_id"])


def downgrade() -> None:
    for table in (
        "consensus_replays",
        "consensus_cost_history",
        "consensus_historical_quality",
        "provider_weights",
        "consensus_metrics",
        "consensus_merge_decisions",
        "consensus_judge_decisions",
        "consensus_evaluation_scores",
        "consensus_candidates",
        "consensus_runs",
    ):
        op.drop_table(table)
