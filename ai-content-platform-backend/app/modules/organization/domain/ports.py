"""Organization module ports — no ORM imports."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.organization.domain.records import OrgMemberRecord, OrganizationRecord


class OrganizationRepository(Protocol):
    """Port for organization persistence."""

    async def get_by_id(self, org_id: uuid.UUID) -> OrganizationRecord | None: ...

    async def get_by_slug(self, slug: str) -> OrganizationRecord | None: ...

    async def list_members(self, org_id: uuid.UUID) -> list[OrgMemberRecord]: ...
