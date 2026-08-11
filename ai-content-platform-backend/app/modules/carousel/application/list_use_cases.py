"""Carousel list/get use cases."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.infrastructure.postgres.models.carousel import CarouselDeck, CarouselSlide, Export


class ListCarouselsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(CarouselDeck)
                .where(CarouselDeck.organization_id == org_id)
                .order_by(CarouselDeck.created_at.desc())
            )
        ).scalars().all()
        return [
            {
                "id": str(d.id),
                "title": d.title,
                "slides_count": d.slide_count,
                "status": d.status,
                "draft_id": str(d.draft_id),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ]


class GetCarouselUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, deck_id: uuid.UUID) -> dict[str, Any]:
        deck = await self._session.get(CarouselDeck, deck_id)
        if deck is None or deck.organization_id != org_id:
            raise NotFoundError("Carousel", str(deck_id))
        slides = (
            await self._session.execute(
                select(CarouselSlide)
                .where(CarouselSlide.deck_id == deck_id)
                .order_by(CarouselSlide.sort_order)
            )
        ).scalars().all()
        exports = (
            await self._session.execute(select(Export).where(Export.deck_id == deck_id))
        ).scalars().all()
        return {
            "id": str(deck.id),
            "title": deck.title,
            "status": deck.status,
            "slides": [
                {
                    "role": s.role,
                    "sort_order": s.sort_order,
                    "structured": s.structured_json,
                    "object_key": s.rendered_object_key,
                }
                for s in slides
            ],
            "exports": [
                {"format": e.format, "size": e.size, "object_key": e.object_key}
                for e in exports
            ],
        }
