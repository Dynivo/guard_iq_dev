"""Organization use cases: get org details, list members."""

from __future__ import annotations

import uuid

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.modules.organization.domain.ports import OrganizationRepository

logger = get_logger(__name__)


class GetOrganizationUseCase:
    """Retrieve an organization by ID."""

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._org_repo = org_repo

    async def execute(self, org_id: uuid.UUID) -> dict:
        org = await self._org_repo.get_by_id(org_id)
        if org is None:
            raise NotFoundError("Organization", str(org_id))
        return {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "is_active": org.is_active,
        }


class ListMembersUseCase:
    """List all active members of an organization."""

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._org_repo = org_repo

    async def execute(self, org_id: uuid.UUID) -> list[dict]:
        members = await self._org_repo.list_members(org_id)
        return [
            {
                "user_id": str(m.user_id),
                "role": m.role,
                "display_name": m.display_name,
                "email": m.email,
            }
            for m in members
        ]
