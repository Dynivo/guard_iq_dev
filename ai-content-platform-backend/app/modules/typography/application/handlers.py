"""Workflow handlers for Brand & Typography Engine."""

from __future__ import annotations

from app.modules.typography.application.factory import TypographyFactory
from app.modules.typography.domain.models import (
    BrandApplication,
    LayoutEnrichment,
    TypographyCopy,
    TypographyPipelineRequest,
    TypographyPlan,
)
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


class _Base:
    def __init__(self, engine=None) -> None:
        self._engine = engine or TypographyFactory.create_memory()


class LayoutPlanHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        layout_plan = context.get("image.layout") or context.get("layout_plan") or {}
        width = int(context.get("target_width") or 1080)
        height = int(context.get("target_height") or 1350)
        enriched = self._engine._layout.enrich(
            layout_plan if isinstance(layout_plan, dict) else {},
            width=width,
            height=height,
        )
        payload = {"typography.layout": enriched.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class TypographyPlanHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        layout = LayoutEnrichment.from_dict(context.get("typography.layout") or {})
        copy_raw = context.get("typography.copy") or {}
        copy = TypographyCopy(
            headline=str(copy_raw.get("headline") or context.get("draft.hook") or ""),
            subtitle=str(copy_raw.get("subtitle") or ""),
            cta=str(copy_raw.get("cta") or context.get("draft.cta") or ""),
            footer=str(copy_raw.get("footer") or ""),
        )
        brand = BrandApplication.from_dict(context.get("typography.brand") or {})
        plan = self._engine._planner.plan(
            layout,
            copy,
            brand=brand if brand.brand_name else None,
            template_id=str(context.get("template_id") or "default"),
        )
        payload = {"typography.plan": plan.to_dict(), "typography.copy": copy.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class BrandApplyHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        kit = context.get("brand_kit") or context.get("image.brand") or {}
        variant = str(context.get("brand_variant") or "dark")
        brand = self._engine._brand.apply(kit if isinstance(kit, dict) else {}, variant=variant)
        payload = {"typography.brand": brand.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class TypographyRenderHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        layout = LayoutEnrichment.from_dict(context.get("typography.layout") or {})
        plan = TypographyPlan.from_dict(context.get("typography.plan") or {})
        brand = BrandApplication.from_dict(context.get("typography.brand") or {})
        copy_raw = context.get("typography.copy") or {}
        copy = TypographyCopy(
            headline=str(copy_raw.get("headline") or ""),
            subtitle=str(copy_raw.get("subtitle") or ""),
            cta=str(copy_raw.get("cta") or ""),
            footer=str(copy_raw.get("footer") or ""),
        )
        asset = self._engine._renderer.render(
            layout=layout,
            plan=plan,
            brand=brand,
            copy=copy,
            illustration_ref=str(context.get("illustration_ref") or ""),
        )
        payload = {
            "typography.asset": asset.to_dict(),
            "typography.svg": asset.svg,
            "typography.layers": [layer.to_dict() for layer in asset.layers],
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs={"typography.layer_count": len(asset.layers)})


class OverlayValidateHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.typography.domain.models import TypographyAsset

        raw = context.get("typography.asset") or {}
        asset = TypographyAsset(
            asset_id=str(raw.get("asset_id") or ""),
            svg=str(raw.get("svg") or ""),
            layers=tuple(),
            width=int(raw.get("width") or 1080),
            height=int(raw.get("height") or 1350),
        )
        # Prefer live object from context if rendered in same engine run via pipeline
        layout = LayoutEnrichment.from_dict(context.get("typography.layout") or {})
        plan = TypographyPlan.from_dict(context.get("typography.plan") or {})
        brand = BrandApplication.from_dict(context.get("typography.brand") or {})
        # Re-hydrate layers
        from app.modules.typography.domain.models import SvgLayer

        layers = tuple(
            SvgLayer.from_dict(x) for x in (raw.get("layers") or []) if isinstance(x, dict)
        )
        asset.layers = layers
        result = self._engine._overlay.validate(asset, layout, plan, brand)
        payload = {"typography.overlay_validation": result.to_dict()}
        context.update(payload)
        if not result.passed:
            return NodeOutcome(success=False, outputs=payload, error_message="overlay validation failed")
        return NodeOutcome(success=True, outputs=payload)


class BrandValidateHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.typography.domain.models import SvgLayer, TypographyAsset

        raw = context.get("typography.asset") or {}
        layers = tuple(
            SvgLayer.from_dict(x) for x in (raw.get("layers") or []) if isinstance(x, dict)
        )
        asset = TypographyAsset(
            asset_id=str(raw.get("asset_id") or ""),
            svg=str(raw.get("svg") or ""),
            layers=layers,
            width=int(raw.get("width") or 1080),
            height=int(raw.get("height") or 1350),
        )
        brand = BrandApplication.from_dict(context.get("typography.brand") or {})
        plan = TypographyPlan.from_dict(context.get("typography.plan") or {})
        result = self._engine._brand_val.validate(brand, asset, plan)
        payload = {"typography.brand_validation": result.to_dict()}
        context.update(payload)
        if not result.passed:
            return NodeOutcome(success=False, outputs=payload, error_message="brand validation failed")
        return NodeOutcome(success=True, outputs=payload)


class TypographyComposeHandler(_Base):
    """Metadata-only node — never renders carousel/PDF slides."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.typography.domain.models import SvgLayer, TypographyAsset

        raw = context.get("typography.asset") or {}
        layers = tuple(
            SvgLayer.from_dict(x) for x in (raw.get("layers") or []) if isinstance(x, dict)
        )
        asset = TypographyAsset(
            asset_id=str(raw.get("asset_id") or ""),
            svg=str(raw.get("svg") or ""),
            layers=layers,
            width=int(raw.get("width") or 1080),
            height=int(raw.get("height") or 1350),
            metadata=dict(raw.get("metadata") or {}),
        )
        layout = LayoutEnrichment.from_dict(context.get("typography.layout") or {})
        plan = TypographyPlan.from_dict(context.get("typography.plan") or {})
        copy_raw = context.get("typography.copy") or {}
        copy = TypographyCopy(
            headline=str(copy_raw.get("headline") or ""),
            subtitle=str(copy_raw.get("subtitle") or ""),
            cta=str(copy_raw.get("cta") or ""),
            footer=str(copy_raw.get("footer") or ""),
        )
        intelligence = self._engine._intelligence.score(
            plan=plan,
            copy=copy,
            layout=layout,
            layer_count=len(layers),
        )
        slide = self._engine._slide_composer.plan(
            asset=asset,
            layout=layout,
            copy=copy,
            template_id=str(context.get("template_id") or plan.template_id or "default"),
        )
        asset_payload = dict(raw)
        asset_payload["slide_composition"] = slide.to_dict()
        asset_payload["intelligence"] = intelligence.to_dict()
        payload = {
            "typography.asset": asset_payload,
            "typography.slide_composition": slide.to_dict(),
            "typography.intelligence": intelligence.to_dict(),
        }
        context.update(payload)
        return NodeOutcome(
            success=True,
            outputs={
                "typography.compose": True,
                "renders_carousel": False,
                "preferred_slide_type": slide.preferred_slide_type,
            },
        )


class TypographyStoreHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.typography.domain.models import (
            SlideCompositionMetadata,
            SvgLayer,
            TypographyAsset,
            TypographyIntelligence,
        )

        raw = context.get("typography.asset")
        if not isinstance(raw, dict):
            return NodeOutcome(success=False, outputs={}, error_message="missing typography asset")
        layers = tuple(
            SvgLayer.from_dict(x) for x in (raw.get("layers") or []) if isinstance(x, dict)
        )
        asset = TypographyAsset(
            asset_id=str(raw.get("asset_id") or ""),
            svg=str(raw.get("svg") or ""),
            layers=layers,
            width=int(raw.get("width") or 1080),
            height=int(raw.get("height") or 1350),
            slide_composition=SlideCompositionMetadata.from_dict(
                raw.get("slide_composition") or context.get("typography.slide_composition")
            ),
            intelligence=TypographyIntelligence.from_dict(
                raw.get("intelligence") or context.get("typography.intelligence")
            ),
            metadata=dict(raw.get("metadata") or {}),
        )
        stored = await self._engine._store.store(asset)
        payload = {"typography.stored": True, "typography.asset_id": stored.asset_id}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class TypographyPipelineHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        copy_raw = context.get("typography.copy") or {}
        req = TypographyPipelineRequest(
            organization_id=str(context.get("organization_id") or "org"),
            draft_id=str(context.get("draft_id") or "draft"),
            image_job_id=str(context.get("image_job_id") or ""),
            layout_plan=context.get("image.layout")
            if isinstance(context.get("image.layout"), dict)
            else (context.get("layout_plan") or {}),
            brand_kit=context.get("brand_kit") if isinstance(context.get("brand_kit"), dict) else {},
            copy=TypographyCopy(
                headline=str(copy_raw.get("headline") or context.get("draft.hook") or "Headline"),
                subtitle=str(copy_raw.get("subtitle") or ""),
                cta=str(copy_raw.get("cta") or context.get("draft.cta") or ""),
                footer=str(copy_raw.get("footer") or ""),
            ),
            illustration_ref=str(context.get("illustration_ref") or ""),
            target_width=int(context.get("target_width") or 1080),
            target_height=int(context.get("target_height") or 1350),
            brand_variant=str(context.get("brand_variant") or "dark"),
            template_id=str(context.get("template_id") or "default"),
        )
        result = await self._engine.run(req)
        payload = {"typography.result": result.to_dict(), "typography.status": result.status}
        context.update(payload)
        ok = result.status == "completed"
        return NodeOutcome(success=ok, outputs=payload, error_message=None if ok else result.status)


def register_typography_handlers(node_registry, engine=None) -> None:
    eng = engine or TypographyFactory.create_memory()
    node_registry.register("layout.plan", LayoutPlanHandler(eng))
    node_registry.register("typography.plan", TypographyPlanHandler(eng))
    node_registry.register("brand.apply", BrandApplyHandler(eng))
    node_registry.register("typography.render", TypographyRenderHandler(eng))
    node_registry.register("overlay.validate", OverlayValidateHandler(eng))
    node_registry.register("brand.validate", BrandValidateHandler(eng))
    node_registry.register("typography.compose", TypographyComposeHandler(eng))
    node_registry.register("typography.store", TypographyStoreHandler(eng))
    node_registry.register("typography.pipeline", TypographyPipelineHandler(eng))
