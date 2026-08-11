"""M12 Carousel Composition & Rendering Engine tables.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("carousel_decks", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("carousel_decks", sa.Column("parent_deck_id", UUID(as_uuid=True), nullable=True))
    op.add_column("carousel_decks", sa.Column("deck_metadata_json", JSONB(), nullable=True))
    op.create_index("ix_carousel_decks_parent_deck_id", "carousel_decks", ["parent_deck_id"])

    op.add_column("carousel_slides", sa.Column("svg_object_key", sa.String(length=512), nullable=True))
    op.add_column("carousel_slides", sa.Column("composition_json", JSONB(), nullable=True))
    op.add_column("carousel_slides", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    op.create_table(
        "carousel_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True),
        sa.Column("deck_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent_asset_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deck_json", JSONB(), nullable=True),
        sa.Column("rendered_json", JSONB(), nullable=True),
        sa.Column("exports_json", JSONB(), nullable=True),
        sa.Column("typography_asset_ids", JSONB(), nullable=True),
        sa.Column("image_refs", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("render_time_ms", sa.Integer(), nullable=True),
        sa.Column("export_time_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_carousel_assets_organization_id", "carousel_assets", ["organization_id"])
    op.create_index("ix_carousel_assets_draft_id", "carousel_assets", ["draft_id"])
    op.create_index("ix_carousel_assets_deck_id", "carousel_assets", ["deck_id"])
    op.create_index("ix_carousel_assets_parent_asset_id", "carousel_assets", ["parent_asset_id"])

    op.create_table(
        "deck_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deck_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_version", sa.Integer(), nullable=True),
        sa.Column("deck_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_deck_versions_organization_id", "deck_versions", ["organization_id"])
    op.create_index("ix_deck_versions_deck_id", "deck_versions", ["deck_id"])

    op.create_table(
        "render_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deck_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("render_time_ms", sa.Integer(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_render_jobs_organization_id", "render_jobs", ["organization_id"])
    op.create_index("ix_render_jobs_deck_id", "render_jobs", ["deck_id"])

    op.create_table(
        "export_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deck_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("formats", JSONB(), nullable=True),
        sa.Column("export_time_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_export_jobs_organization_id", "export_jobs", ["organization_id"])
    op.create_index("ix_export_jobs_deck_id", "export_jobs", ["deck_id"])

    op.create_table(
        "export_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deck_id", UUID(as_uuid=True), nullable=True),
        sa.Column("export_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("slide_index", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_export_artifacts_organization_id", "export_artifacts", ["organization_id"])
    op.create_index("ix_export_artifacts_deck_id", "export_artifacts", ["deck_id"])
    op.create_index("ix_export_artifacts_export_job_id", "export_artifacts", ["export_job_id"])


def downgrade() -> None:
    op.drop_index("ix_export_artifacts_export_job_id", table_name="export_artifacts")
    op.drop_index("ix_export_artifacts_deck_id", table_name="export_artifacts")
    op.drop_index("ix_export_artifacts_organization_id", table_name="export_artifacts")
    op.drop_table("export_artifacts")
    op.drop_index("ix_export_jobs_deck_id", table_name="export_jobs")
    op.drop_index("ix_export_jobs_organization_id", table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_index("ix_render_jobs_deck_id", table_name="render_jobs")
    op.drop_index("ix_render_jobs_organization_id", table_name="render_jobs")
    op.drop_table("render_jobs")
    op.drop_index("ix_deck_versions_deck_id", table_name="deck_versions")
    op.drop_index("ix_deck_versions_organization_id", table_name="deck_versions")
    op.drop_table("deck_versions")
    op.drop_index("ix_carousel_assets_parent_asset_id", table_name="carousel_assets")
    op.drop_index("ix_carousel_assets_deck_id", table_name="carousel_assets")
    op.drop_index("ix_carousel_assets_draft_id", table_name="carousel_assets")
    op.drop_index("ix_carousel_assets_organization_id", table_name="carousel_assets")
    op.drop_table("carousel_assets")
    op.drop_column("carousel_slides", "version")
    op.drop_column("carousel_slides", "composition_json")
    op.drop_column("carousel_slides", "svg_object_key")
    op.drop_index("ix_carousel_decks_parent_deck_id", table_name="carousel_decks")
    op.drop_column("carousel_decks", "deck_metadata_json")
    op.drop_column("carousel_decks", "parent_deck_id")
    op.drop_column("carousel_decks", "version")
