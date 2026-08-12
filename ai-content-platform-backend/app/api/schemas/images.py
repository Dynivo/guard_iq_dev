"""Image generation request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateImagesRequest(BaseModel):
    """Optional override for how many LinkedIn images to generate."""

    count: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="Number of images (default from brand kit / configs/image/generation.yaml)",
    )
    guidance: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional image direction, e.g. 'show a care home manager with a growth chart'",
    )
    provider: str | None = Field(
        default=None,
        max_length=40,
        description="Override which image model to use for this generation, e.g. 'openai' or 'gemini'. Defaults to IMAGE_PROVIDER.",
    )
    providers: list[str] | None = Field(
        default=None,
        max_length=4,
        description="Generate one variant per provider (e.g. ['openai', 'gemini']) so they can be compared side by side. Overrides count and provider when set.",
    )
