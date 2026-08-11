"""Standard API response envelope.

Every API response uses `{data, error, meta: {request_id}}` so the
frontend can handle success and failure uniformly.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaInfo(BaseModel):
    request_id: str = ""


class ApiResponse(BaseModel, Generic[T]):
    """Uniform envelope for all API responses."""

    data: T | None = None
    error: str | None = None
    meta: MetaInfo = Field(default_factory=MetaInfo)


def success_response(data: Any, request_id: str = "") -> dict:
    """Build a success envelope dict."""
    return {"data": data, "error": None, "meta": {"request_id": request_id}}


def error_response(message: str, request_id: str = "") -> dict:
    """Build an error envelope dict."""
    return {"data": None, "error": message, "meta": {"request_id": request_id}}
