"""Pydantic schemas for the intelligence API."""

from __future__ import annotations

from pydantic import BaseModel


class RescoreResponse(BaseModel):
    """Response from the rescore endpoint."""

    article_id: str
    score: int
    status: str
    sector: str | None = None
    framework: str | None = None
    angle: str | None = None
    reason: str | None = None
    embedded: bool = False
