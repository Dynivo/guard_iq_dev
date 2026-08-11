"""News module request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArticleResponse(BaseModel):
    id: str
    organization_id: str
    source_id: str
    title: str
    summary: str | None = None
    url: str
    published_at: str | None = None
    author: str | None = None
    status: str
    created_at: str


class ArticleListResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    limit: int
    offset: int


class SourceResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    connector_type: str
    config_json: dict[str, Any]
    schedule_cron: str | None = None
    enabled: bool
    last_fetched_at: str | None = None
    created_at: str


class CreateSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    connector_type: str = Field(min_length=1, max_length=50)
    config_json: dict[str, Any] = Field(default_factory=dict)
    schedule_cron: str | None = None
    category: str | None = None
    credibility_score: int | None = Field(default=None, ge=0, le=100)
    priority: int | None = Field(default=None, ge=0, le=100)
    api_key_name: str | None = None


class UpdateSourceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config_json: dict[str, Any] | None = None
    schedule_cron: str | None = None
    enabled: bool | None = None
    category: str | None = None
    credibility_score: int | None = Field(default=None, ge=0, le=100)
    priority: int | None = Field(default=None, ge=0, le=100)


class RunSourceResponse(BaseModel):
    job_id: str
    status: str
    source_id: str
    source_name: str
