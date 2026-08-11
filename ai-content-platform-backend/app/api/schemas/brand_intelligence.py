"""Pydantic schemas for Brand Intelligence API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateProfileRequest(BaseModel):
    kind: str = "corporate"
    name: str = "Corporate"
    is_default: bool = False


class CreateImportRequest(BaseModel):
    brand_profile_id: UUID
    linkedin_url: str | None = None
    linkedin_about: str | None = None
    linkedin_headline: str | None = None
    linkedin_display_name: str | None = None
    linkedin_posts: list[Any] = Field(default_factory=list)
    website_url: str | None = None
    max_pages: int = 8
    use_playwright: bool = True
    max_posts: int = Field(default=40, ge=1, le=100)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class LinkedInUrlImportRequest(BaseModel):
    """Product path: paste LinkedIn URL only → fetch + analyze."""

    linkedin_url: str = Field(..., min_length=12)
    brand_profile_id: UUID | None = None
    profile_name: str | None = None
    max_posts: int = Field(default=40, ge=1, le=100)
    website_url: str | None = None


class NeverSayUpdateRequest(BaseModel):
    forbidden: list[str] | None = None
    discouraged: list[str] | None = None
    legal_restrictions: list[str] | None = None
    compliance_restrictions: list[str] | None = None
    avoid_vocabulary: list[str] | None = None
    never_use: list[str] | None = None
    preferred_alternatives: dict[str, str] | None = None


class ReviewEditRequest(BaseModel):
    edits: dict[str, Any] = Field(default_factory=dict)


class LinkedInSessionStartRequest(BaseModel):
    note: str | None = "Open Playwright profile and complete LinkedIn login once."


class LogoVariantRequest(BaseModel):
    variant: str = "primary"
    storage_key: str
    make_primary: bool = True
