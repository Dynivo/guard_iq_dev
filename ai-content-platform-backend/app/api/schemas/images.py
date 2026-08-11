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
