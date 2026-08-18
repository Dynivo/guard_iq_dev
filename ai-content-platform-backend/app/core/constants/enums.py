"""Domain enumerations used across modules."""

from __future__ import annotations

from enum import StrEnum


class MembershipRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ArticleStatus(StrEnum):
    RAW = "raw"
    NORMALIZED = "normalized"
    DUPLICATE = "duplicate"
    SCORED = "scored"
    SCREENING = "screening"
    RELEVANT = "relevant"
    REFERENCE = "reference"
    IRRELEVANT = "irrelevant"
    USED = "used"


class DraftStatus(StrEnum):
    PLANNING = "planning"
    GENERATING = "generating"
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class ContentType(StrEnum):
    EDUCATIONAL = "educational"
    SUCCESS_STORY = "success_story"
    PERSONAL_ACHIEVEMENT = "personal_achievement"
    REGULATORY_UPDATE = "regulatory_update"
    THREAT_ALERT = "threat_alert"


class PhotoMode(StrEnum):
    HAS_PHOTOS = "has_photos"
    TAKE_NOW = "take_now"
    JOB_PLANNED = "job_planned"
    NONE = "none"


class ConnectorType(StrEnum):
    RSS = "rss"
    NEWS_API = "news_api"
    GOVERNMENT = "government"
    BLOG = "blog"


class ImageJobStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    UPSCALING = "upscaling"
    QUALITY_CHECK = "quality_check"
    TYPOGRAPHY = "typography"
    COMPLETE = "complete"
    FAILED = "failed"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    RETRYING = "retrying"


class FeedbackAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class SlideRole(StrEnum):
    HOOK = "hook"
    CONTEXT = "context"
    PROBLEM = "problem"
    EXPLANATION = "explanation"
    RECOMMENDATION = "recommendation"
    SUMMARY = "summary"
    CTA = "cta"
