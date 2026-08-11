"""Carousel Composition & Rendering Engine ports (M12 + M12r)."""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.carousel.domain.models import (
    AssetDependencyGraph,
    CarouselAsset,
    CarouselPlan,
    CarouselPipelineRequest,
    CarouselPipelineResult,
    CarouselReplayRecord,
    Deck,
    DeckDefinition,
    DeckDiff,
    DeckOptimizationResult,
    ExportArtifact,
    RenderedDeck,
    RenderPlan,
    SlideComposition,
    SlideDiff,
)


class CarouselPlanner(Protocol):
    def plan(
        self,
        draft_snapshot: dict[str, Any],
        *,
        typography_assets: tuple[dict[str, Any], ...] = (),
        image_refs: tuple[str, ...] = (),
    ) -> CarouselPlan: ...


class SlideCompositionEngine(Protocol):
    def compose(
        self,
        plan: CarouselPlan,
        *,
        typography_assets: tuple[dict[str, Any], ...] = (),
        image_refs: tuple[str, ...] = (),
    ) -> tuple[SlideComposition, ...]: ...


class DeckBuilder(Protocol):
    def build(
        self,
        plan: CarouselPlan,
        compositions: tuple[SlideComposition, ...],
        *,
        title: str = "",
        parent_deck_id: str | None = None,
        version: int = 1,
    ) -> Deck: ...


class DeckDefinitionBuilder(Protocol):
    def build(
        self,
        deck: Deck,
        *,
        draft_id: str = "",
        typography_asset_ids: tuple[str, ...] = (),
        image_refs: tuple[str, ...] = (),
        export_profile_id: str = "linkedin",
        width: int | None = None,
        height: int | None = None,
        extra_safe_areas: tuple[dict, ...] = (),
    ) -> DeckDefinition: ...


class DeckOptimizer(Protocol):
    def optimize(self, definition: DeckDefinition) -> DeckOptimizationResult: ...


class RenderPlanner(Protocol):
    def prepare(
        self,
        deck: Deck,
        *,
        width: int = 1080,
        height: int = 1350,
        export_formats: tuple[str, ...] = ("png", "pdf", "zip"),
        export_profile_id: str = "linkedin",
        definition: DeckDefinition | None = None,
    ) -> RenderPlan: ...


class CarouselRenderer(Protocol):
    async def render(self, definition: DeckDefinition) -> RenderedDeck: ...


class ExportEngine(Protocol):
    async def export(
        self,
        rendered: RenderedDeck,
        *,
        formats: tuple[str, ...] = ("png", "pdf", "zip"),
    ) -> tuple[ExportArtifact, ...]: ...


class CarouselAssetStore(Protocol):
    async def store(self, asset: CarouselAsset) -> CarouselAsset: ...

    def get(self, asset_id: str) -> CarouselAsset | None: ...

    def history(self, asset_id: str) -> list[CarouselAsset]: ...


class CarouselReplayStore(Protocol):
    def save(self, record: CarouselReplayRecord) -> None: ...

    def get(self, replay_id: str) -> CarouselReplayRecord | None: ...


class DeckDiffService(Protocol):
    def diff_decks(self, left: Deck, right: Deck) -> DeckDiff: ...

    def diff_slides(self, left_slide: Any, right_slide: Any) -> SlideDiff: ...


class CarouselEngine(Protocol):
    async def run(self, request: CarouselPipelineRequest) -> CarouselPipelineResult: ...
