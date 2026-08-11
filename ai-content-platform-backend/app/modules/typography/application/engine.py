"""Brand & Typography Engine facade (M11) — SVG assets; no carousel/PDF."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.modules.typography.application.assets import InMemoryTypographyAssetStore
from app.modules.typography.application.brand_engine import DefaultBrandEngine
from app.modules.typography.application.brand_validator import DefaultBrandValidator
from app.modules.typography.application.cache import TypographyCacheBundle
from app.modules.typography.application.intelligence import DefaultTypographyIntelligenceScorer
from app.modules.typography.application.layout_enrich import DefaultLayoutEnricher
from app.modules.typography.application.metrics import (
    InMemoryTypographyMetrics,
    TypographyMetricsSnapshot,
)
from app.modules.typography.application.overlay_validator import DefaultOverlayValidator
from app.modules.typography.application.planner import DefaultTypographyPlanner
from app.modules.typography.application.renderer import DefaultTypographyRenderer
from app.modules.typography.application.replay import (
    DefaultOverlayDiffService,
    InMemoryTypographyReplayStore,
)
from app.modules.typography.application.slide_composition import DefaultSlideCompositionPlanner
from app.modules.typography.domain.models import (
    TypographyPipelineRequest,
    TypographyPipelineResult,
    TypographyReplayRecord,
)
from app.modules.typography.domain.ports import (
    BrandEngine,
    BrandValidator,
    LayoutEnricher,
    OverlayValidator,
    SlideCompositionPlanner,
    TypographyAssetStore,
    TypographyIntelligenceScorer,
    TypographyPlanner,
    TypographyRenderer,
)

logger = get_logger(__name__)


class DefaultBrandTypographyEngine:
    def __init__(
        self,
        *,
        layout_enricher: LayoutEnricher | None = None,
        planner: TypographyPlanner | None = None,
        brand_engine: BrandEngine | None = None,
        renderer: TypographyRenderer | None = None,
        overlay_validator: OverlayValidator | None = None,
        brand_validator: BrandValidator | None = None,
        intelligence_scorer: TypographyIntelligenceScorer | None = None,
        slide_composer: SlideCompositionPlanner | None = None,
        asset_store: TypographyAssetStore | None = None,
        cache: TypographyCacheBundle | None = None,
        metrics: InMemoryTypographyMetrics | None = None,
        replay_store: InMemoryTypographyReplayStore | None = None,
        config_dir: Path | None = None,
        brand_config_dir: Path | None = None,
    ) -> None:
        self._layout = layout_enricher or DefaultLayoutEnricher(config_dir)
        self._planner = planner or DefaultTypographyPlanner(config_dir)
        self._brand = brand_engine or DefaultBrandEngine(brand_config_dir)
        self._renderer = renderer or DefaultTypographyRenderer(config_dir)
        self._overlay = overlay_validator or DefaultOverlayValidator(config_dir)
        self._brand_val = brand_validator or DefaultBrandValidator(brand_config_dir)
        self._intelligence = intelligence_scorer or DefaultTypographyIntelligenceScorer(config_dir)
        self._slide_composer = slide_composer or DefaultSlideCompositionPlanner(config_dir)
        self._store = asset_store or InMemoryTypographyAssetStore()
        self._cache = cache or TypographyCacheBundle()
        self._metrics = metrics or InMemoryTypographyMetrics()
        self._replay = replay_store or InMemoryTypographyReplayStore()
        self._diff = DefaultOverlayDiffService()

    @property
    def store(self) -> TypographyAssetStore:
        return self._store

    @property
    def replay_store(self) -> InMemoryTypographyReplayStore:
        return self._replay

    @property
    def diff_service(self) -> DefaultOverlayDiffService:
        return self._diff

    async def run(self, request: TypographyPipelineRequest) -> TypographyPipelineResult:
        started = time.perf_counter()
        layout_key = f"{request.target_width}x{request.target_height}:{hash(str(request.layout_plan))}"
        layout = self._cache.layout.get(layout_key)
        if layout is None:
            layout = self._layout.enrich(
                request.layout_plan,
                width=request.target_width,
                height=request.target_height,
            )
            self._cache.layout.put(layout_key, layout)

        brand_key = f"{request.brand_kit.get('id')}:{request.brand_variant}"
        brand = self._cache.brand.get(brand_key)
        if brand is None:
            brand = self._brand.apply(request.brand_kit, variant=request.brand_variant)
            self._cache.brand.put(brand_key, brand)

        plan = self._planner.plan(
            layout,
            request.copy,
            brand=brand,
            template_id=request.template_id,
        )
        render_started = time.perf_counter()
        asset = self._renderer.render(
            layout=layout,
            plan=plan,
            brand=brand,
            copy=request.copy,
            illustration_ref=request.illustration_ref,
            logo_options=request.logo_options,
            logo_data_uri=request.logo_data_uri,
        )
        render_ms = int((time.perf_counter() - render_started) * 1000)

        val_started = time.perf_counter()
        overlay = self._overlay.validate(asset, layout, plan, brand)
        brand_val = self._brand_val.validate(brand, asset, plan)
        val_ms = int((time.perf_counter() - val_started) * 1000)

        asset.overlay_validation = overlay
        asset.brand_validation = brand_val

        intelligence = self._intelligence.score(
            plan=plan,
            copy=request.copy,
            layout=layout,
            layer_count=len(asset.layers),
        )
        slide_composition = self._slide_composer.plan(
            asset=asset,
            layout=layout,
            copy=request.copy,
            template_id=request.template_id,
        )
        asset.intelligence = intelligence
        asset.slide_composition = slide_composition
        asset.metadata = {
            **asset.metadata,
            "organization_id": request.organization_id,
            "draft_id": request.draft_id,
            "image_job_id": request.image_job_id,
            "correlation_id": request.correlation_id,
            "replay_of_asset_id": request.replay_of_asset_id,
            "design_tokens": brand.design_tokens.to_dict() if brand.design_tokens else None,
            "typography_intelligence": intelligence.to_dict(),
            "slide_composition": slide_composition.to_dict(),
        }
        if request.replay_of_asset_id:
            asset.parent_asset_id = request.replay_of_asset_id
            parent = self._store.get(request.replay_of_asset_id)
            asset.version = (parent.version + 1) if parent else 2

        if not overlay.passed or not brand_val.passed:
            status = "validation_failed"
        else:
            status = "completed"
            await self._store.store(asset)

        result = TypographyPipelineResult(
            asset=asset,
            status=status,
            render_time_ms=render_ms,
            validation_time_ms=val_ms,
            slide_composition=slide_composition,
            intelligence=intelligence,
            metadata={
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "reasons": list(overlay.reason_codes) + list(brand_val.reason_codes),
            },
        )
        self._replay.save(
            TypographyReplayRecord(
                replay_id=str(uuid.uuid4()),
                asset_id=asset.asset_id,
                request_snapshot={
                    "organization_id": request.organization_id,
                    "draft_id": request.draft_id,
                    "layout_plan": request.layout_plan,
                    "brand_kit": request.brand_kit,
                    "copy": request.copy.to_dict(),
                    "target_width": request.target_width,
                    "target_height": request.target_height,
                    "brand_variant": request.brand_variant,
                    "template_id": request.template_id,
                    "illustration_ref": request.illustration_ref,
                },
                result_snapshot=result.to_dict(),
            )
        )
        self._metrics.record(
            TypographyMetricsSnapshot(
                render_time_ms=render_ms,
                validation_time_ms=val_ms,
                accessibility_score=overlay.accessibility_score,
                brand_score=brand_val.brand_score,
                typography_score=overlay.typography_score,
                contrast_score=overlay.contrast_score,
                overflow_rate=overlay.overflow_rate,
            )
        )
        if status != "completed":
            logger.warning(
                "typography_validation_failed",
                extra={"asset_id": asset.asset_id, "reasons": result.metadata.get("reasons")},
            )
            # Still raise only if hard-fail desired; return result for API
        return result

    async def replay(self, replay_id: str) -> TypographyPipelineResult:
        record = self._replay.get(replay_id)
        if record is None:
            raise ValidationError(f"Typography replay not found: {replay_id}")
        snap = record.request_snapshot
        from app.modules.typography.domain.models import TypographyCopy

        req = TypographyPipelineRequest(
            organization_id=str(snap.get("organization_id") or ""),
            draft_id=str(snap.get("draft_id") or ""),
            layout_plan=dict(snap.get("layout_plan") or {}),
            brand_kit=dict(snap.get("brand_kit") or {}),
            copy=TypographyCopy(
                headline=str((snap.get("copy") or {}).get("headline") or ""),
                subtitle=str((snap.get("copy") or {}).get("subtitle") or ""),
                cta=str((snap.get("copy") or {}).get("cta") or ""),
                footer=str((snap.get("copy") or {}).get("footer") or ""),
            ),
            illustration_ref=str(snap.get("illustration_ref") or ""),
            target_width=int(snap.get("target_width") or 1080),
            target_height=int(snap.get("target_height") or 1350),
            brand_variant=str(snap.get("brand_variant") or "dark"),
            template_id=str(snap.get("template_id") or "default"),
            replay_of_asset_id=record.asset_id,
        )
        return await self.run(req)
