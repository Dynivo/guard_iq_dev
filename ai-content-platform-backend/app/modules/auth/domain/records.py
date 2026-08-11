"""Domain records for auth ports — no ORM imports in domain."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class UserRecord:
    id: uuid.UUID
    email: str
    display_name: str
    password_hash: str
    is_active: bool
    organization_id: uuid.UUID


@dataclass(frozen=True)
class MembershipRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    is_active: bool
