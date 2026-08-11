"""Brand Intelligence domain models — no ORM."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProfileKind(StrEnum):
    CORPORATE = "corporate"
    HEALTHCARE = "healthcare"
    LEGAL = "legal"
    ACCOUNTING = "accounting"
    CYBER = "cyber"
    FINANCE = "finance"
    CUSTOM = "custom"


class CboObjectType(StrEnum):
    PROFILE = "profile"
    POST = "post"
    PAGE = "page"
    DOCUMENT = "document"
    EMAIL = "email"
    MEDIA = "media"
    GUIDELINE = "guideline"
    OTHER = "other"


class CboSourceType(StrEnum):
    LINKEDIN = "linkedin"
    WEBSITE = "website"
    UPLOAD = "upload"
    EMAIL = "email"
    YOUTUBE = "youtube"
    MEDIUM = "medium"
    SUBSTACK = "substack"
    WORDPRESS = "wordpress"
    GHOST = "ghost"
    HUBSPOT = "hubspot"
    RSS = "rss"
    OTHER = "other"


class ImportStatus(StrEnum):
    PENDING = "pending"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    AWAITING_VALIDATION = "awaiting_validation"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class MemoryLifecycle(StrEnum):
    DRAFT = "draft"
    AWAITING_VALIDATION = "awaiting_validation"
    FINALIZED = "finalized"
    REJECTED = "rejected"


class PersonaKind(StrEnum):
    CEO = "ceo"
    FOUNDER = "founder"
    TECHNICAL = "technical"
    MARKETING = "marketing"
    SALES = "sales"
    INVESTOR = "investor"
    RECRUITMENT = "recruitment"
    CUSTOM = "custom"


@dataclass(slots=True)
class BrandProfile:
    id: uuid.UUID
    organization_id: uuid.UUID
    kind: ProfileKind
    name: str
    is_default: bool = False
    active_memory_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class BrandPersona:
    id: uuid.UUID
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    kind: PersonaKind
    name: str
    is_default: bool = False
    voice_notes: str = ""
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NeverSayPolicy:
    id: uuid.UUID
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    forbidden: list[str] = field(default_factory=list)
    discouraged: list[str] = field(default_factory=list)
    legal_restrictions: list[str] = field(default_factory=list)
    compliance_restrictions: list[str] = field(default_factory=list)
    avoid_vocabulary: list[str] = field(default_factory=list)
    never_use: list[str] = field(default_factory=list)
    preferred_alternatives: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalBrandObject:
    id: uuid.UUID
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    import_id: uuid.UUID | None
    object_type: CboObjectType
    source_type: CboSourceType
    external_id: str | None = None
    canonical_url: str | None = None
    fingerprint: str = ""
    title: str | None = None
    body_text: str | None = None
    html_sanitized: str | None = None
    authored_at: datetime | None = None
    language: str | None = None
    media_refs: list[dict[str, Any]] = field(default_factory=list)
    engagement: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrandImport:
    id: uuid.UUID
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    status: ImportStatus
    source_mix_json: dict[str, Any] = field(default_factory=dict)
    watermark_json: dict[str, Any] = field(default_factory=dict)
    last_sync_at: datetime | None = None
    error_json: dict[str, Any] | None = None


@dataclass(slots=True)
class BrandImportJob:
    id: uuid.UUID
    organization_id: uuid.UUID
    import_id: uuid.UUID
    job_id: uuid.UUID | None
    stage: str
    progress_pct: int = 0
    message: str = ""
    error_json: dict[str, Any] | None = None
    eta_seconds: int | None = None


@dataclass(slots=True)
class BrandCompletenessReport:
    writing: float = 0.0
    visual: float = 0.0
    logo: float = 0.0
    topic_coverage: float = 0.0
    audience_coverage: float = 0.0
    vocabulary_coverage: float = 0.0
    cta_coverage: float = 0.0
    guidelines_coverage: float = 0.0
    website_coverage: float = 0.0
    linkedin_coverage: float = 0.0
    confidence: float = 0.0
    overall_brand_score: float = 0.0


@dataclass(slots=True)
class BrandHealthReport:
    overall_health: float = 0.0
    consistency: float = 0.0
    visual_consistency: float = 0.0
    writing_consistency: float = 0.0
    voice_consistency: float = 0.0
    audience_confidence: float = 0.0
    topic_diversity: float = 0.0
    asset_coverage: float = 0.0
    guideline_coverage: float = 0.0
    missing_assets: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BrandRecommendation:
    code: str
    title: str
    detail: str
    priority: int = 50


@dataclass(slots=True)
class BrandMemoryDraft:
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    brand_dna: dict[str, Any] = field(default_factory=dict)
    writing_dna: dict[str, Any] = field(default_factory=dict)
    visual_dna: dict[str, Any] = field(default_factory=dict)
    engagement_json: dict[str, Any] = field(default_factory=dict)
    topics: list[dict[str, Any]] = field(default_factory=list)
    hooks: list[dict[str, Any]] = field(default_factory=list)
    ctas: list[dict[str, Any]] = field(default_factory=list)
    vocabulary: dict[str, Any] = field(default_factory=dict)
    detected: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass(slots=True)
class BrandMemory:
    id: uuid.UUID
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    version_no: int
    lifecycle: MemoryLifecycle
    confidence: float
    brand_dna_json: dict[str, Any] = field(default_factory=dict)
    writing_dna_json: dict[str, Any] = field(default_factory=dict)
    visual_dna_json: dict[str, Any] = field(default_factory=dict)
    engagement_json: dict[str, Any] = field(default_factory=dict)
    completeness_json: dict[str, Any] = field(default_factory=dict)
    health_json: dict[str, Any] = field(default_factory=dict)
    recommendations_json: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class BrandMemoryVersion:
    id: uuid.UUID
    organization_id: uuid.UUID
    memory_id: uuid.UUID
    version_no: int
    snapshot_json: dict[str, Any]
    created_by: uuid.UUID | None = None


@dataclass(slots=True)
class BrandMemoryReview:
    id: uuid.UUID
    organization_id: uuid.UUID
    memory_id: uuid.UUID
    status: str
    detections_json: dict[str, Any] = field(default_factory=dict)
    edits_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LogoAssetSet:
    id: uuid.UUID
    organization_id: uuid.UUID
    brand_profile_id: uuid.UUID
    variants_json: dict[str, str] = field(default_factory=dict)
    primary_key: str | None = None


@dataclass(slots=True)
class BrowserSessionRecord:
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    ciphertext: bytes
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
