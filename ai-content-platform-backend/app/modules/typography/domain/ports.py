"""Brand & Typography Engine ports (M11)."""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.typography.domain.models import (
    BrandApplication,
    BrandValidationResult,
    LayoutEnrichment,
    LogoPlacementOptions,
    OverlayDiff,
    OverlayValidationResult,
    SlideCompositionMetadata,
    TypographyAsset,
    TypographyCopy,
    TypographyIntelligence,
    TypographyPipelineRequest,
    TypographyPipelineResult,
    TypographyPlan,
    TypographyReplayRecord,
)


class LayoutEnricher(Protocol):
    def enrich(
        self,
        layout_plan: dict[str, Any],
        *,
        width: int,
        height: int,
    ) -> LayoutEnrichment: ...


class TypographyPlanner(Protocol):
    def plan(
        self,
        layout: LayoutEnrichment,
        copy: TypographyCopy,
        *,
        brand: BrandApplication | None = None,
        template_id: str = "default",
    ) -> TypographyPlan: ...


class BrandEngine(Protocol):
    def apply(
        self,
        brand_kit: dict[str, Any],
        *,
        variant: str = "dark",
    ) -> BrandApplication: ...


class TypographyRenderer(Protocol):
    def render(
        self,
        *,
        layout: LayoutEnrichment,
        plan: TypographyPlan,
        brand: BrandApplication,
        copy: TypographyCopy,
        illustration_ref: str = "",
        logo_options: LogoPlacementOptions | None = None,
        logo_data_uri: str | None = None,
    ) -> TypographyAsset: ...


class OverlayValidator(Protocol):
    def validate(
        self,
        asset: TypographyAsset,
        layout: LayoutEnrichment,
        plan: TypographyPlan,
        brand: BrandApplication,
    ) -> OverlayValidationResult: ...


class BrandValidator(Protocol):
    def validate(
        self,
        brand: BrandApplication,
        asset: TypographyAsset,
        plan: TypographyPlan,
    ) -> BrandValidationResult: ...


class TypographyAssetStore(Protocol):
    async def store(self, asset: TypographyAsset) -> TypographyAsset: ...

    def get(self, asset_id: str) -> TypographyAsset | None: ...

    def history(self, asset_id: str) -> list[TypographyAsset]: ...


class TypographyReplayStore(Protocol):
    def save(self, record: TypographyReplayRecord) -> None: ...

    def get(self, replay_id: str) -> TypographyReplayRecord | None: ...


class OverlayDiffService(Protocol):
    def diff(self, left: TypographyAsset, right: TypographyAsset) -> OverlayDiff: ...


class TypographyIntelligenceScorer(Protocol):
    def score(
        self,
        *,
        plan: TypographyPlan,
        copy: TypographyCopy,
        layout: LayoutEnrichment,
        layer_count: int = 0,
    ) -> TypographyIntelligence: ...


class SlideCompositionPlanner(Protocol):
    def plan(
        self,
        *,
        asset: TypographyAsset,
        layout: LayoutEnrichment,
        copy: TypographyCopy,
        template_id: str = "default",
    ) -> SlideCompositionMetadata: ...


class BrandTypographyEngine(Protocol):
    async def run(self, request: TypographyPipelineRequest) -> TypographyPipelineResult: ...
