"""M11 Brand & Typography Engine tables.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "typography_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True),
        sa.Column("image_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent_asset_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("svg_text", sa.Text(), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("layers_json", JSONB(), nullable=True),
        sa.Column("layout_enrichment_json", JSONB(), nullable=True),
        sa.Column("typography_plan_json", JSONB(), nullable=True),
        sa.Column("brand_application_json", JSONB(), nullable=True),
        sa.Column("overlay_validation_json", JSONB(), nullable=True),
        sa.Column("brand_validation_json", JSONB(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("accessibility_score", sa.Float(), nullable=True),
        sa.Column("brand_score", sa.Float(), nullable=True),
        sa.Column("typography_score", sa.Float(), nullable=True),
        sa.Column("contrast_score", sa.Float(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_typography_assets_organization_id", "typography_assets", ["organization_id"])
    op.create_index("ix_typography_assets_draft_id", "typography_assets", ["draft_id"])
    op.create_index("ix_typography_assets_image_job_id", "typography_assets", ["image_job_id"])
    op.create_index("ix_typography_assets_parent_asset_id", "typography_assets", ["parent_asset_id"])

    op.create_table(
        "typography_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("template_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("config_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_typography_templates_template_key", "typography_templates", ["template_key"])


def downgrade() -> None:
    op.drop_index("ix_typography_templates_template_key", table_name="typography_templates")
    op.drop_table("typography_templates")
    op.drop_index("ix_typography_assets_parent_asset_id", table_name="typography_assets")
    op.drop_index("ix_typography_assets_image_job_id", table_name="typography_assets")
    op.drop_index("ix_typography_assets_draft_id", table_name="typography_assets")
    op.drop_index("ix_typography_assets_organization_id", table_name="typography_assets")
    op.drop_table("typography_assets")
