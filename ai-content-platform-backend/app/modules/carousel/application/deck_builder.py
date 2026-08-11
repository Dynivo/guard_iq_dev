"""Deck builder — slide objects, navigation, metadata."""

from __future__ import annotations

from app.modules.carousel.domain.models import (
    CarouselPlan,
    Deck,
    DeckSlide,
    SlideComposition,
    new_id,
)


class DefaultDeckBuilder:
    def build(
        self,
        plan: CarouselPlan,
        compositions: tuple[SlideComposition, ...],
        *,
        title: str = "",
        parent_deck_id: str | None = None,
        version: int = 1,
    ) -> Deck:
        comp_by_index = {c.slide_index: c for c in compositions}
        slide_ids = [new_id() for _ in plan.slides]
        slides: list[DeckSlide] = []
        for i, planned in enumerate(plan.slides):
            slides.append(
                DeckSlide(
                    slide_id=slide_ids[i],
                    index=i,
                    purpose=planned.purpose,
                    title=planned.title,
                    body=planned.body,
                    composition=comp_by_index.get(planned.index) or comp_by_index.get(i),
                    prev_slide_id=slide_ids[i - 1] if i > 0 else None,
                    next_slide_id=slide_ids[i + 1] if i + 1 < len(slide_ids) else None,
                    transition_hint=planned.transition_hint,
                    version=version,
                    metadata={
                        "preferred_layout": planned.preferred_layout,
                        "continuation_hint": planned.continuation_hint,
                        "typography_asset_id": planned.typography_asset_id,
                        "image_ref": planned.image_ref,
                    },
                )
            )
        return Deck(
            deck_id=new_id(),
            title=title or (plan.slides[0].title if plan.slides else "Carousel"),
            slides=tuple(slides),
            version=version,
            parent_deck_id=parent_deck_id,
            metadata={
                "slide_count": len(slides),
                "sequence": list(plan.sequence),
                "mutates_content": False,
            },
        )
