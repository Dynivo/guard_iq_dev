"""Brand Intelligence schema.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brand_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False, server_default="corporate"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active_memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_profiles_organization_id", "brand_profiles", ["organization_id"])

    op.create_table(
        "brand_personas",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("voice_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_personas_organization_id", "brand_personas", ["organization_id"])
    op.create_index("ix_brand_personas_brand_profile_id", "brand_personas", ["brand_profile_id"])

    op.create_table(
        "brand_never_say_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forbidden", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("discouraged", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("legal_restrictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("compliance_restrictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("avoid_vocabulary", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("never_use", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("preferred_alternatives", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_profile_id"),
    )
    op.create_index("ix_brand_never_say_policies_organization_id", "brand_never_say_policies", ["organization_id"])

    op.create_table(
        "brand_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("source_mix_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("watermark_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_imports_organization_id", "brand_imports", ["organization_id"])
    op.create_index("ix_brand_imports_brand_profile_id", "brand_imports", ["brand_profile_id"])

    op.create_table(
        "brand_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(80), nullable=False, server_default="pending"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_json", postgresql.JSONB(), nullable=True),
        sa.Column("eta_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_import_jobs_organization_id", "brand_import_jobs", ["organization_id"])
    op.create_index("ix_brand_import_jobs_import_id", "brand_import_jobs", ["import_id"])
    op.create_index("ix_brand_import_jobs_job_id", "brand_import_jobs", ["job_id"])

    op.create_table(
        "canonical_brand_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_imports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("html_sanitized", sa.Text(), nullable=True),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("media_refs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("engagement", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_canonical_brand_objects_organization_id", "canonical_brand_objects", ["organization_id"])
    op.create_index("ix_canonical_brand_objects_import_id", "canonical_brand_objects", ["import_id"])
    op.create_index("ix_canonical_brand_objects_fingerprint", "canonical_brand_objects", ["fingerprint"])

    op.create_table(
        "brand_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifecycle", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("brand_dna_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("writing_dna_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("visual_dna_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("engagement_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("completeness_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("health_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendations_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_profile_id"),
    )
    op.create_index("ix_brand_memories_organization_id", "brand_memories", ["organization_id"])

    op.create_table(
        "brand_memory_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_memory_versions_organization_id", "brand_memory_versions", ["organization_id"])
    op.create_index("ix_brand_memory_versions_memory_id", "brand_memory_versions", ["memory_id"])

    op.create_table(
        "brand_memory_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("detections_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("edits_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_memory_reviews_organization_id", "brand_memory_reviews", ["organization_id"])
    op.create_index("ix_brand_memory_reviews_memory_id", "brand_memory_reviews", ["memory_id"])

    op.create_table(
        "brand_logo_asset_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variants_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("primary_key", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("brand_profile_id"),
    )
    op.create_index("ix_brand_logo_asset_sets_organization_id", "brand_logo_asset_sets", ["organization_id"])

    op.create_table(
        "brand_browser_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_browser_sessions_organization_id", "brand_browser_sessions", ["organization_id"])

    op.create_table(
        "brand_vector_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding_ref", sa.String(200), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brand_vector_chunks_organization_id", "brand_vector_chunks", ["organization_id"])
    op.create_index("ix_brand_vector_chunks_brand_profile_id", "brand_vector_chunks", ["brand_profile_id"])
    op.create_index("ix_brand_vector_chunks_memory_id", "brand_vector_chunks", ["memory_id"])


def downgrade() -> None:
    for table in (
        "brand_vector_chunks",
        "brand_browser_sessions",
        "brand_logo_asset_sets",
        "brand_memory_reviews",
        "brand_memory_versions",
        "brand_memories",
        "canonical_brand_objects",
        "brand_import_jobs",
        "brand_imports",
        "brand_never_say_policies",
        "brand_personas",
        "brand_profiles",
    ):
        op.drop_table(table)
