"""News pipeline models: sources, articles, deduplication, clustering, topics."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class NewsSource(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "news_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authority: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.5)
    reliability: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.5)
    trust: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.5)
    failure_rate: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    circuit_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    credibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=70)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True, default=50)
    api_key_name: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Article(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("organization_id", "url"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("news_sources.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    normalized_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="raw")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    topic_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ArticleRawPayload(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "article_raw_payloads"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id"), nullable=False, index=True
    )
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SeenUrl(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "seen_urls"
    __table_args__ = (UniqueConstraint("organization_id", "url_hash"),)

    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)


class TopicCluster(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "topic_clusters"

    label: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cohesion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timeline_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    members: Mapped[list["ClusterMember"]] = []  # populated via query


class ClusterMember(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cluster_members"
    __table_args__ = (UniqueConstraint("cluster_id", "article_id"),)

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("topic_clusters.id"), nullable=False, index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id"), nullable=False, index=True
    )
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class Topic(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ArticleEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "article_entities"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True, index=True
    )
    article_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ArticleEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "article_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True, index=True
    )
    article_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class NewsTopicTrend(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "news_topic_trends"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    topic_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    window_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class StoryTimelineRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "story_timelines"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    story_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    article_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    events: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cohesion: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at_story: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class SourceFeedbackEventRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_feedback_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    article_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
