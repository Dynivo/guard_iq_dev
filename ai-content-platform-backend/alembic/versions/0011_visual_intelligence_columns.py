"""M10 Visual Intelligence — image job enrichment + workflow registry audit.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("image_jobs", sa.Column("prompt_hash", sa.String(length=64), nullable=True))
    op.add_column("image_jobs", sa.Column("workflow_id", sa.String(length=100), nullable=True))
    op.add_column("image_jobs", sa.Column("workflow_version", sa.String(length=30), nullable=True))
    op.add_column("image_jobs", sa.Column("scene_plan_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("composition_plan_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("policy_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("validation_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("prompt_request_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("generation_metadata_json", JSONB(), nullable=True))
    op.add_column("image_jobs", sa.Column("queue_time_ms", sa.Integer(), nullable=True))
    op.add_column("image_jobs", sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("image_jobs", sa.Column("replay_of_job_id", UUID(as_uuid=True), nullable=True))

    op.create_table(
        "image_workflow_registry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("graph_path", sa.String(length=512), nullable=False),
        sa.Column("parameters_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_image_workflow_registry_workflow_id", "image_workflow_registry", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_image_workflow_registry_workflow_id", table_name="image_workflow_registry")
    op.drop_table("image_workflow_registry")
    for col in (
        "replay_of_job_id",
        "retry_count",
        "queue_time_ms",
        "generation_metadata_json",
        "prompt_request_json",
        "validation_json",
        "policy_json",
        "composition_plan_json",
        "scene_plan_json",
        "workflow_version",
        "workflow_id",
        "prompt_hash",
    ):
        op.drop_column("image_jobs", col)
