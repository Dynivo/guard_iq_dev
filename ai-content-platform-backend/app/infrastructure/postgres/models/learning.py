"""Learning system models: examples, rules, writing preferences, feedback, review, history."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.session import Base
from app.infrastructure.postgres.models.mixins import (
    OrgScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class _KnowledgeMetricsMixin:
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    approval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_from_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(40), default="candidate", nullable=False)


class Example(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin, _KnowledgeMetricsMixin):
    __tablename__ = "examples"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class Rule(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin, _KnowledgeMetricsMixin):
    __tablename__ = "rules"

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class WritingPreference(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin, _KnowledgeMetricsMixin
):
    __tablename__ = "writing_preferences"

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    preference: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class KnowledgeSignalRow(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin, _KnowledgeMetricsMixin
):
    __tablename__ = "knowledge_signals"

    category: Mapped[str] = mapped_column(String(100), nullable=False, default="signal")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(80), nullable=False, default="generic")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class FeedbackEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "feedback_events"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewSessionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "review_sessions"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version_refs_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ReviewAssignmentRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "review_assignments"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="reviewer")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="assigned")
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ReviewCommentRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "review_comments"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class ReviewDecisionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "review_decisions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    decision_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_codes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    categories_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    policy_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ReviewHistoryRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "review_history"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class ReviewerProfileRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "reviewer_profiles"

    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    review_accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_edit_distance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approval_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rejection_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    specializations_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recommendation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approvals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    edits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    edit_distance_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class LearningEventRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "learning_events"

    source_event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    review_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PreferenceUpdateRow(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "preference_updates"

    preference_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    previous_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    source_learning_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
