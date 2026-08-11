"""Legacy CarouselWorkflow — delegates to CarouselGenerationService (M12)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.carousel.application.service import CarouselGenerationService


class CarouselWorkflow:
    """Backward-compatible entrypoint used by older imports/tests."""

    def __init__(self, session: AsyncSession, **_kwargs: Any) -> None:
        self._service = CarouselGenerationService(session)

    async def execute(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        size: str = "1080x1350",
    ) -> dict[str, Any]:
        return await self._service.generate(org_id, draft_id, size=size)
