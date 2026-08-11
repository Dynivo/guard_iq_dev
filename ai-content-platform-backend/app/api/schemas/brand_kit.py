"""Brand kit request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BrandKitResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    primary_color: str
    secondary_color: str
    accent_color: str | None = None
    font_heading: str
    font_body: str
    logo_object_key: str | None = None
    tone_json: dict[str, Any] | None = None
    footer_text: str | None = None
    services_line: str | None = None
    client_profile_path: str | None = None
    client_profile_md: str | None = None
    description: str | None = None
    extra_settings: dict[str, Any] | None = None
    default_image_count: int | None = None
    auto_generate_image_with_draft: bool | None = None
    publishing_window: str | None = None
    publishing_targets: dict[str, int] | None = None


class BrandKitUpdateRequest(BaseModel):
    name: str | None = None
    primary_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_heading: str | None = None
    font_body: str | None = None
    footer_text: str | None = None
    services_line: str | None = None
    description: str | None = None
    tone_json: dict[str, Any] | None = None
    client_profile_md: str | None = Field(
        default=None,
        max_length=100_000,
        description="Org brand profile Markdown used for relevance + draft generation",
    )
    extra_settings: dict[str, Any] | None = None
    default_image_count: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="Convenience field merged into extra_settings.default_image_count",
    )
    auto_generate_image_with_draft: bool | None = Field(
        default=None,
        description="When true, queue LinkedIn image generation right after a draft is created",
    )
    publishing_window: str | None = Field(
        default=None,
        pattern=r"^(weekly|fortnight)$",
        description="Publishing mix window: weekly (Mon–Fri) or fortnight (10 workdays)",
    )
    publishing_targets: dict[str, int] | None = Field(
        default=None,
        description="Optional mix overrides: educational, success_story, personal_achievement",
    )


class BrandProfileTemplateResponse(BaseModel):
    generator_prompt: str
    outline: str
    section_headings: list[str]
