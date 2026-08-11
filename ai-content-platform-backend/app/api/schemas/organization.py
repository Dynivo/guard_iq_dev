"""Organization request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    created_at: str


class MemberResponse(BaseModel):
    user_id: str
    organization_id: str
    role: str
    is_active: bool
    display_name: str | None = None
    email: str | None = None
