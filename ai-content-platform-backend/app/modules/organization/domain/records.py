"""Domain records for organization module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OrganizationRecord:
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    settings_json: dict[str, Any] | None


@dataclass(frozen=True)
class OrgMemberRecord:
    user_id: uuid.UUID
    email: str
    display_name: str
    role: str


@dataclass(frozen=True)
class BrandKitRecord:
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    primary_color: str
    secondary_color: str
    accent_color: str | None
    font_heading: str
    font_body: str
    logo_object_key: str | None
    tone_json: dict[str, Any] | None
    footer_text: str | None
    services_line: str | None
    client_profile_path: str | None
    client_profile_md: str | None
    extra_settings: dict[str, Any] | None
    description: str | None
