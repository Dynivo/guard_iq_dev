"""Carousel engine facade — compose existing assets; never mutate draft/typography/images."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.modules.carousel.application.assets import InMemoryCarouselAssetStore
from app.modules.carousel.application.cache import CarouselCacheBundle
from app.modules.carousel.application.composition import DefaultSlideCompositionEngine
from app.modules.carousel.application.deck_builder import DefaultDeckBuilder
from app.modules.carousel.application.deck_definition import DefaultDeckDefinitionBuilder
from app.modules.carousel.application.dependency_graph import DefaultAssetDependencyGraphBuilder
from app.modules.carousel.application.export_engine import DefaultExportEngine
from app.modules.carousel.application.export_profiles import ExportProfileRegistry
from app.modules.carousel.application.metrics import (
    CarouselMetricsSnapshot,
    InMemoryCarouselMetrics,
)
from app.modules.carousel.application.optimizer import DefaultDeckOptimizer
from app.modules.carousel.application.planner import DefaultCarouselPlanner
from app.modules.carousel.application.render_planner import DefaultRenderPlanner
from app.modules.carousel.application.renderer import (
    MockCarouselRenderer,
    PlaywrightCarouselRenderer,
)
from app.modules.carousel.application.replay import (
    DefaultDeckDiffService,
    InMemoryCarouselReplayStore,
)
from app.modules.carousel.domain.models import (
    CarouselAsset,
    CarouselPipelineRequest,
    CarouselPipelineResult,
    CarouselReplayRecord,
    new_id,
)
from app.modules.carousel.domain.ports import (
    CarouselAssetStore,
    CarouselPlanner,
    CarouselRenderer,
    DeckBuilder,
    DeckDefinitionBuilder,
    DeckOptimizer,
    ExportEngine,
    RenderPlanner,
    SlideCompositionEngine,
)

logger = get_logger(__name__)


class DefaultCarouselEngine:
    def __init__(
        self,
        *,
        planner: CarouselPlanner | None = None,
        composer: SlideCompositionEngine | None = None,
        deck_builder: DeckBuilder | None = None,
        definition_builder: DeckDefinitionBuilder | None = None,
        optimizer: DeckOptimizer | None = None,
        render_planner: RenderPlanner | None = None,
        renderer: CarouselRenderer | None = None,
        export_engine: ExportEngine | None = None,
        asset_store: CarouselAssetStore | None = None,
        cache: CarouselCacheBundle | None = None,
        metrics: InMemoryCarouselMetrics | None = None,
        replay_store: InMemoryCarouselReplayStore | None = None,
        config_dir: Path | None = None,
        use_mock_renderer: bool = True,
    ) -> None:
        self._planner = planner or DefaultCarouselPlanner(config_dir)
        self._composer = composer or DefaultSlideCompositionEngine(config_dir)
        self._deck = deck_builder or DefaultDeckBuilder()
        self._definition = definition_builder or DefaultDeckDefinitionBuilder(config_dir)
        self._optimizer = optimizer or DefaultDeckOptimizer(config_dir)
        self._deps = DefaultAssetDependencyGraphBuilder()
        self._profiles = ExportProfileRegistry(config_dir)
        self._render_planner = render_planner or DefaultRenderPlanner(config_dir)
        if renderer is not None:
            self._renderer = renderer
        elif use_mock_renderer:
            self._renderer = MockCarouselRenderer()
        else:
            self._renderer = PlaywrightCarouselRenderer()
        self._export = export_engine or DefaultExportEngine(config_dir)
        self._store = asset_store or InMemoryCarouselAssetStore()
        self._cache = cache or CarouselCacheBundle()
        self._metrics = metrics or InMemoryCarouselMetrics()
        self._replay = replay_store or InMemoryCarouselReplayStore()
        self._diff = DefaultDeckDiffService()
        self._use_mock = use_mock_renderer

    @property
    def store(self) -> CarouselAssetStore:
        return self._store

    @property
    def replay_store(self) -> InMemoryCarouselReplayStore:
        return self._replay

    @property
    def diff_service(self) -> DefaultDeckDiffService:
        return self._diff

    async def run(self, request: CarouselPipelineRequest) -> CarouselPipelineResult:
        started = time.perf_counter()
        draft = dict(request.draft_snapshot)
        draft_fingerprint = {
            "hook": draft.get("hook"),
            "cta": draft.get("cta"),
            "carousel": draft.get("carousel"),
            "generated_text": draft.get("generated_text"),
            "edited_text": draft.get("edited_text"),
        }

        plan = self._planner.plan(
            draft,
            typography_assets=request.typography_assets,
            image_refs=request.image_refs,
        )
        compositions = self._composer.compose(
            plan,
            typography_assets=request.typography_assets,
            image_refs=request.image_refs,
        )

        version = 1
        parent_deck_id = None
        if request.replay_of_asset_id:
            parent = self._store.get(request.replay_of_asset_id)
            if parent:
                version = parent.version + 1
                parent_deck_id = parent.deck.deck_id

        title = str(draft.get("hook") or "Carousel")
        deck = self._deck.build(
            plan,
            compositions,
            title=title,
            parent_deck_id=parent_deck_id,
            version=version,
        )
        self._cache.deck.put(deck.deck_id, deck)

        typo_ids = tuple(
            str(a.get("asset_id")) for a in request.typography_assets if a.get("asset_id")
        )
        profile_id = request.export_profile or "linkedin"
        profile = self._profiles.get(profile_id)
        extra_safe = tuple(
            sa
            for c in compositions
            for sa in c.safe_areas
            if isinstance(sa, dict)
        )

        # Prefer request size when explicitly square or custom; else profile
        width, height = request.target_width, request.target_height
        if width == 1080 and height == 1350:
            width, height = profile.width, profile.height

        definition = self._definition.build(
            deck,
            draft_id=request.draft_id,
            typography_asset_ids=typo_ids,
            image_refs=request.image_refs,
            export_profile_id=profile.profile_id,
            width=width,
            height=height,
            extra_safe_areas=extra_safe,
        )
        optimization = self._optimizer.optimize(definition)
        definition.optimization = optimization
        definition.metadata = {
            **definition.metadata,
            "optimization": optimization.to_dict(),
        }

        render_plan = self._render_planner.prepare(
            deck,
            width=definition.width,
            height=definition.height,
            export_formats=request.export_formats or profile.formats,
            export_profile_id=profile.profile_id,
            definition=definition,
        )
        # Align definition strategy with plan
        definition.render_strategy = render_plan.strategy

        renderer = self._renderer
        if request.use_mock_renderer and not isinstance(renderer, MockCarouselRenderer):
            renderer = MockCarouselRenderer()

        render_started = time.perf_counter()
        render_failures = 0
        try:
            rendered = await renderer.render(definition)
        except Exception as exc:  # noqa: BLE001
            logger.warning("carousel_render_failed", extra={"error": str(exc)})
            render_failures = 1
            rendered = await MockCarouselRenderer().render(definition)
        render_ms = int((time.perf_counter() - render_started) * 1000)
        self._cache.render.put(deck.deck_id, rendered)

        formats = request.export_formats or profile.formats
        export_started = time.perf_counter()
        exports = await self._export.export(rendered, formats=formats)
        export_ms = int((time.perf_counter() - export_started) * 1000)
        self._cache.export.put(deck.deck_id, exports)

        after_fingerprint = {
            "hook": draft.get("hook"),
            "cta": draft.get("cta"),
            "carousel": draft.get("carousel"),
            "generated_text": draft.get("generated_text"),
            "edited_text": draft.get("edited_text"),
        }
        if after_fingerprint != draft_fingerprint:
            raise ValidationError("Carousel engine must not mutate draft content")

        asset_id = new_id()
        dependency_graph = self._deps.build(
            draft_id=request.draft_id,
            typography_asset_ids=typo_ids,
            carousel_asset_id=asset_id,
            export_artifacts=exports,
        )

        png_size = sum(e.size_bytes for e in exports if e.format == "png")
        pdf_size = sum(e.size_bytes for e in exports if e.format == "pdf")
        export_size = sum(e.size_bytes or len(e.content) for e in exports)

        asset = CarouselAsset(
            asset_id=asset_id,
            deck=deck,
            rendered=rendered,
            exports=exports,
            deck_definition=definition,
            dependency_graph=dependency_graph,
            optimization=optimization,
            export_profile=profile.profile_id,
            typography_asset_ids=typo_ids,
            image_refs=request.image_refs,
            version=version,
            parent_asset_id=request.replay_of_asset_id,
            status="completed",
            metadata={
                "organization_id": request.organization_id,
                "draft_id": request.draft_id,
                "correlation_id": request.correlation_id,
                "mutates_draft": False,
                "mutates_typography": False,
                "mutates_images": False,
                "calls_llm": False,
                "calls_image_model": False,
                "editable_sot": "deck_definition",
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        await self._store.store(asset)

        result = CarouselPipelineResult(
            asset=asset,
            status="completed",
            plan=plan,
            render_plan=render_plan,
            deck_definition=definition,
            optimization=optimization,
            dependency_graph=dependency_graph,
            render_time_ms=render_ms,
            export_time_ms=export_ms,
            metadata={
                "slide_count": len(deck.slides),
                "export_count": len(exports),
                "render_failures": render_failures,
                "export_profile": profile.profile_id,
            },
        )
        self._replay.save(
            CarouselReplayRecord(
                replay_id=str(uuid.uuid4()),
                asset_id=asset.asset_id,
                request_snapshot={
                    "organization_id": request.organization_id,
                    "draft_id": request.draft_id,
                    "draft_snapshot": draft_fingerprint,
                    "typography_asset_ids": list(typo_ids),
                    "image_refs": list(request.image_refs),
                    "target_width": request.target_width,
                    "target_height": request.target_height,
                    "export_formats": list(formats),
                    "export_profile": profile.profile_id,
                    "dependency_graph": dependency_graph.to_dict(),
                },
                result_snapshot=result.to_dict(),
            )
        )
        self._metrics.record(
            CarouselMetricsSnapshot(
                render_time_ms=render_ms,
                export_time_ms=export_ms,
                slide_count=len(deck.slides),
                export_size_bytes=export_size,
                pdf_size_bytes=pdf_size,
                png_size_bytes=png_size,
                render_failures=render_failures,
            )
        )
        return result

    async def replay(self, replay_id: str) -> CarouselPipelineResult:
        record = self._replay.get(replay_id)
        if record is None:
            raise ValidationError(f"Carousel replay not found: {replay_id}")
        snap = record.request_snapshot
        # Re-bind draft + typography refs from dependency graph when present
        graph = snap.get("dependency_graph") or {}
        typo_ids = list(snap.get("typography_asset_ids") or [])
        if not typo_ids and isinstance(graph, dict):
            for node in graph.get("nodes") or []:
                if isinstance(node, dict) and node.get("kind") == "typography" and node.get("ref"):
                    typo_ids.append(str(node["ref"]))
        req = CarouselPipelineRequest(
            organization_id=str(snap.get("organization_id") or ""),
            draft_id=str(snap.get("draft_id") or ""),
            draft_snapshot=dict(snap.get("draft_snapshot") or {}),
            image_refs=tuple(str(x) for x in (snap.get("image_refs") or ())),
            target_width=int(snap.get("target_width") or 1080),
            target_height=int(snap.get("target_height") or 1350),
            export_formats=tuple(
                str(x) for x in (snap.get("export_formats") or ("png", "pdf", "zip"))
            ),
            export_profile=str(snap.get("export_profile") or "linkedin"),
            replay_of_asset_id=record.asset_id,
            use_mock_renderer=True,
        )
        return await self.run(req)
