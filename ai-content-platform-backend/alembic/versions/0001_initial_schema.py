"""Initial schema — all platform tables.

Revision ID: 0001
Revises: None
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Identity / Security ──────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("settings_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("permission_id", UUID(as_uuid=True), sa.ForeignKey("permissions.id"), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "organization_id"),
    )
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])

    # ── Branding ─────────────────────────────────────────────
    op.create_table(
        "brand_kits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("primary_color", sa.String(20), nullable=False, server_default=sa.text("'#003366'")),
        sa.Column("secondary_color", sa.String(20), nullable=False, server_default=sa.text("'#FFFFFF'")),
        sa.Column("accent_color", sa.String(20), nullable=True),
        sa.Column("font_heading", sa.String(100), nullable=False, server_default=sa.text("'Inter'")),
        sa.Column("font_body", sa.String(100), nullable=False, server_default=sa.text("'Inter'")),
        sa.Column("logo_object_key", sa.String(512), nullable=True),
        sa.Column("tone_json", JSONB, nullable=True),
        sa.Column("footer_text", sa.String(500), nullable=True),
        sa.Column("services_line", sa.String(500), nullable=True),
        sa.Column("client_profile_path", sa.String(512), nullable=True),
        sa.Column("extra_settings", JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_brand_kits_organization_id", "brand_kits", ["organization_id"])

    # ── News ─────────────────────────────────────────────────
    op.create_table(
        "news_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("connector_type", sa.String(50), nullable=False),
        sa.Column("config_json", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_news_sources_organization_id", "news_sources", ["organization_id"])

    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("news_sources.id"), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author", sa.String(500), nullable=True),
        sa.Column("normalized_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'raw'")),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "url"),
    )
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_normalized_hash", "articles", ["normalized_hash"])

    op.create_table(
        "article_raw_payloads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("connector_type", sa.String(50), nullable=False),
        sa.Column("raw_json", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_article_raw_payloads_article_id", "article_raw_payloads", ["article_id"])

    op.create_table(
        "seen_urls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "url_hash"),
    )
    op.create_index("ix_seen_urls_url_hash", "seen_urls", ["url_hash"])

    op.create_table(
        "topics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_topics_organization_id", "topics", ["organization_id"])

    op.create_table(
        "topic_clusters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("article_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_topic_clusters_organization_id", "topic_clusters", ["organization_id"])

    op.create_table(
        "cluster_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cluster_id", UUID(as_uuid=True), sa.ForeignKey("topic_clusters.id"), nullable=False),
        sa.Column("article_id", UUID(as_uuid=True), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("similarity_score", sa.Float, nullable=True),
        sa.UniqueConstraint("cluster_id", "article_id"),
    )
    op.create_index("ix_cluster_members_cluster_id", "cluster_members", ["cluster_id"])
    op.create_index("ix_cluster_members_article_id", "cluster_members", ["article_id"])

    # ── Intelligence ─────────────────────────────────────────
    op.create_table(
        "article_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("qdrant_id", sa.String(255), nullable=True),
        sa.Column("dimensions", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_article_embeddings_article_id", "article_embeddings", ["article_id"])

    op.create_table(
        "relevance_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("audience", sa.String(50), nullable=True),
        sa.Column("angle", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_relevance_scores_article_id", "relevance_scores", ["article_id"])

    op.create_table(
        "claims",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("provenance", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Content ──────────────────────────────────────────────
    op.create_table(
        "content_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("angle", sa.Text, nullable=True),
        sa.Column("target_audience", sa.String(100), nullable=True),
        sa.Column("plan_json", JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True),
        sa.Column("content_plan_id", UUID(as_uuid=True), sa.ForeignKey("content_plans.id"), nullable=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("generated_text", sa.Text, nullable=True),
        sa.Column("edited_text", sa.Text, nullable=True),
        sa.Column("hook", sa.String(500), nullable=True),
        sa.Column("cta", sa.String(500), nullable=True),
        sa.Column("hashtags_json", JSONB, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "draft_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("draft_id", UUID(as_uuid=True), sa.ForeignKey("drafts.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_draft_versions_draft_id", "draft_versions", ["draft_id"])

    op.create_table(
        "draft_variations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("draft_id", UUID(as_uuid=True), sa.ForeignKey("drafts.id"), nullable=False),
        sa.Column("variation_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("hook", sa.String(500), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_draft_variations_draft_id", "draft_variations", ["draft_id"])

    op.create_table(
        "prompt_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), sa.ForeignKey("drafts.id"), nullable=True),
        sa.Column("prompt_name", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("input_text", sa.Text, nullable=True),
        sa.Column("output_text", sa.Text, nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Carousel / Media ─────────────────────────────────────
    op.create_table(
        "carousel_decks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("slide_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "carousel_slides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("deck_id", UUID(as_uuid=True), sa.ForeignKey("carousel_decks.id"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("structured_json", JSONB, nullable=True),
        sa.Column("template_id", UUID(as_uuid=True), nullable=True),
        sa.Column("rendered_object_key", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_carousel_slides_deck_id", "carousel_slides", ["deck_id"])

    op.create_table(
        "templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default=sa.text("'carousel'")),
        sa.Column("html_path", sa.String(512), nullable=True),
        sa.Column("preview_object_key", sa.String(512), nullable=True),
        sa.Column("variables_schema", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "media_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("exif_stripped", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "exports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deck_id", UUID(as_uuid=True), sa.ForeignKey("carousel_decks.id"), nullable=True),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("size", sa.String(20), nullable=False, server_default=sa.text("'1080x1350'")),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Image Jobs ───────────────────────────────────────────
    op.create_table(
        "image_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("visual_plan_json", JSONB, nullable=True),
        sa.Column("prompt_enhanced", sa.String(2000), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cost_estimate", sa.Float, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "image_job_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("image_jobs.id"), nullable=False),
        sa.Column("artifact_type", sa.String(50), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_image_job_artifacts_job_id", "image_job_artifacts", ["job_id"])

    # ── Learning ─────────────────────────────────────────────
    op.create_table(
        "examples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=True),
        sa.Column("content_type", sa.String(50), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("hook", sa.String(500), nullable=True),
        sa.Column("tags_json", JSONB, nullable=True),
        sa.Column("weight", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("source_feedback_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "writing_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("preference", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("0.5")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "feedback_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason_category", sa.String(100), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("diff_summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── AI Ops ───────────────────────────────────────────────
    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("variables_schema", JSONB, nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("examples_json", JSONB, nullable=True),
        sa.Column("eval_notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_versions_name", "prompt_versions", ["name"])

    op.create_table(
        "llm_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("input_text", sa.Text, nullable=True),
        sa.Column("output_text", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("cost_estimate", sa.Float, nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'success'")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_calls_correlation_id", "llm_calls", ["correlation_id"])

    op.create_table(
        "provider_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("config_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Jobs ─────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payload_ref", sa.String(512), nullable=True),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("3")),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index("ix_jobs_correlation_id", "jobs", ["correlation_id"])

    op.create_table(
        "job_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])


def downgrade() -> None:
    tables = [
        "job_events", "jobs",
        "provider_configs", "llm_calls", "prompt_versions",
        "feedback_events", "writing_preferences", "rules", "examples",
        "image_job_artifacts", "image_jobs",
        "exports", "media_assets", "templates", "carousel_slides", "carousel_decks",
        "prompt_history", "draft_variations", "draft_versions", "drafts", "content_plans",
        "claims", "relevance_scores", "article_embeddings",
        "cluster_members", "topic_clusters", "topics",
        "seen_urls", "article_raw_payloads", "articles", "news_sources",
        "brand_kits",
        "audit_logs", "sessions", "memberships", "role_permissions",
        "permissions", "roles", "users", "organizations",
    ]
    for table in tables:
        op.drop_table(table)
