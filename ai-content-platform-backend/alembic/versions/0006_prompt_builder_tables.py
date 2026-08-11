"""Extend prompt_versions; add golden cases, eval runs, replay (M7).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prompt_versions",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
    )
    op.add_column(
        "prompt_versions",
        sa.Column(
            "approval_status",
            sa.String(length=30),
            nullable=False,
            server_default="approved",
        ),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("capability", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("schema_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("tags", JSONB(), nullable=True),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("sections_json", JSONB(), nullable=True),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_prompt_versions_capability",
        "prompt_versions",
        ["capability"],
        unique=False,
    )

    op.create_table(
        "prompt_golden_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", sa.String(length=100), nullable=False),
        sa.Column("prompt_name", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("variables", JSONB(), nullable=True),
        sa.Column("expected_contains", JSONB(), nullable=True),
        sa.Column("expected_json_keys", JSONB(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_prompt_golden_cases_prompt_name",
        "prompt_golden_cases",
        ["prompt_name"],
        unique=False,
    )

    op.create_table(
        "prompt_eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("prompt_name", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("suite_name", sa.String(length=255), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("results_json", JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_prompt_eval_runs_prompt_name",
        "prompt_eval_runs",
        ["prompt_name"],
        unique=False,
    )

    op.create_table(
        "prompt_replay",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("replay_id", sa.String(length=100), nullable=False),
        sa.Column("prompt_id", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("compiled_hash", sa.String(length=64), nullable=False),
        sa.Column("compiled_text", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_prompt_replay_replay_id",
        "prompt_replay",
        ["replay_id"],
        unique=True,
    )
    op.create_index(
        "ix_prompt_replay_correlation_id",
        "prompt_replay",
        ["correlation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_replay_correlation_id", table_name="prompt_replay")
    op.drop_index("ix_prompt_replay_replay_id", table_name="prompt_replay")
    op.drop_table("prompt_replay")
    op.drop_index("ix_prompt_eval_runs_prompt_name", table_name="prompt_eval_runs")
    op.drop_table("prompt_eval_runs")
    op.drop_index("ix_prompt_golden_cases_prompt_name", table_name="prompt_golden_cases")
    op.drop_table("prompt_golden_cases")
    op.drop_index("ix_prompt_versions_capability", table_name="prompt_versions")
    op.drop_column("prompt_versions", "metadata_json")
    op.drop_column("prompt_versions", "sections_json")
    op.drop_column("prompt_versions", "tags")
    op.drop_column("prompt_versions", "schema_id")
    op.drop_column("prompt_versions", "capability")
    op.drop_column("prompt_versions", "approval_status")
    op.drop_column("prompt_versions", "status")
