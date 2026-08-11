"""Carousel replay and deck/slide diff."""

from __future__ import annotations

from app.modules.carousel.domain.models import (
    CarouselReplayRecord,
    Deck,
    DeckDiff,
    DeckSlide,
    SlideDiff,
)


class InMemoryCarouselReplayStore:
    def __init__(self) -> None:
        self._items: dict[str, CarouselReplayRecord] = {}

    def save(self, record: CarouselReplayRecord) -> None:
        self._items[record.replay_id] = record

    def get(self, replay_id: str) -> CarouselReplayRecord | None:
        return self._items.get(replay_id)


class DefaultDeckDiffService:
    def diff_decks(self, left: Deck, right: Deck) -> DeckDiff:
        left_map = {s.index: s for s in left.slides}
        right_map = {s.index: s for s in right.slides}
        changes: dict = {}
        for idx in set(left_map) | set(right_map):
            l = left_map.get(idx)
            r = right_map.get(idx)
            if l is None or r is None or l.title != r.title or l.purpose != r.purpose:
                changes[str(idx)] = {
                    "left": l.to_dict() if l else None,
                    "right": r.to_dict() if r else None,
                }
        return DeckDiff(
            left_deck_id=left.deck_id,
            right_deck_id=right.deck_id,
            slide_changes=changes,
            count_changed=len(left.slides) != len(right.slides),
        )

    def diff_slides(self, left_slide: DeckSlide, right_slide: DeckSlide) -> SlideDiff:
        left_layers = {
            L.layer_id: L.to_dict()
            for L in (left_slide.composition.layers if left_slide.composition else ())
        }
        right_layers = {
            L.layer_id: L.to_dict()
            for L in (right_slide.composition.layers if right_slide.composition else ())
        }
        layer_changes: dict = {}
        for lid in set(left_layers) | set(right_layers):
            if left_layers.get(lid) != right_layers.get(lid):
                layer_changes[lid] = {"left": left_layers.get(lid), "right": right_layers.get(lid)}
        return SlideDiff(
            left_slide_id=left_slide.slide_id,
            right_slide_id=right_slide.slide_id,
            purpose_changed=left_slide.purpose != right_slide.purpose,
            title_changed=left_slide.title != right_slide.title,
            layer_changes=layer_changes,
        )
