"""Pydantic schemas for the content/drafts API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateDraftRequest(BaseModel):
    """Request body for generating a draft from an article."""

    content_type: str = Field(default="educational", description="Content type for the post")
    force: bool = Field(
        default=False,
        description="Override soft relevance gate when article is not marked relevant",
    )


class UpdateDraftRequest(BaseModel):
    """Request body for updating a draft (edited text only)."""

    edited_text: str = Field(..., description="The manually edited text")


class RegenerateDraftRequest(BaseModel):
    """Regenerate the full post or one section, with optional client guidance."""

    section: str = Field(
        default="full",
        description="One of: full, hook, body, cta, hashtags, carousel, summary",
    )
    guidance: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional instructions, e.g. 'shorter hook' or 'more about CQC'",
    )


class DraftListItem(BaseModel):
    """Summary item for draft listing."""

    id: str
    article_id: str | None = None
    content_type: str
    status: str
    hook: str | None = None
    generated_text: str | None = None
    version: int
    created_at: str | None = None


class DraftDetail(BaseModel):
    """Full draft detail including variations and M9r enrichment."""

    id: str
    article_id: str | None = None
    content_type: str
    status: str
    generated_text: str | None = None
    edited_text: str | None = None
    hook: str | None = None
    cta: str | None = None
    hashtags: list[str] | None = None
    metadata: dict | None = None
    version: int
    variations: list[dict] = []
    quality: dict | None = None
    visual_brief: dict | None = None
    safety: dict | None = None
    draft_metadata: dict | None = None
    created_at: str | None = None
    updated_at: str | None = None
