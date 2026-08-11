"""Brand kit repository port — no ORM imports."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.modules.organization.domain.records import BrandKitRecord


class BrandKitRepository(Protocol):
    """Port for brand kit persistence."""

    async def get_by_org_id(self, org_id: uuid.UUID) -> BrandKitRecord | None: ...

    async def get_by_id(self, kit_id: uuid.UUID) -> BrandKitRecord | None: ...

    async def update(self, kit_id: uuid.UUID, fields: dict[str, Any]) -> BrandKitRecord | None: ...
