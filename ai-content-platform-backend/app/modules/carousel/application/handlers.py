"""Workflow handlers for Carousel Composition & Rendering Engine."""

from __future__ import annotations

from typing import Any

from app.modules.carousel.application.factory import CarouselFactory
from app.modules.carousel.domain.models import (
    CarouselPlan,
    CarouselPipelineRequest,
    Deck,
    SlideComposition,
)
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


class _Base:
    def __init__(self, engine=None) -> None:
        self._engine = engine or CarouselFactory.create_memory()


def _draft_from_context(context: WorkflowContext) -> dict[str, Any]:
    return (
        context.get("carousel.draft")
        or context.get("draft")
        or context.get("draft_snapshot")
        or {}
    )


def _typography_from_context(context: WorkflowContext) -> tuple[dict, ...]:
    raw = context.get("typography.assets") or context.get("typography_assets") or []
    if isinstance(raw, dict):
        return (raw,)
    return tuple(x for x in raw if isinstance(x, dict))


class CarouselPlanHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        draft = _draft_from_context(context)
        plan = self._engine._planner.plan(
            draft if isinstance(draft, dict) else {},
            typography_assets=_typography_from_context(context),
            image_refs=tuple(str(x) for x in (context.get("image_refs") or ())),
        )
        payload = {"carousel.plan": plan.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs={"carousel.slide_count": plan.slide_count})


class CarouselComposeHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        plan = CarouselPlan.from_dict(context.get("carousel.plan") or {})
        compositions = self._engine._composer.compose(
            plan,
            typography_assets=_typography_from_context(context),
            image_refs=tuple(str(x) for x in (context.get("image_refs") or ())),
        )
        payload = {
            "carousel.compositions": [c.to_dict() for c in compositions],
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs={"carousel.compose": True, "renders": False})


class CarouselBuildHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        plan = CarouselPlan.from_dict(context.get("carousel.plan") or {})
        comps = tuple(
            SlideComposition.from_dict(x)
            for x in (context.get("carousel.compositions") or [])
            if isinstance(x, dict)
        )
        draft = _draft_from_context(context)
        deck = self._engine._deck.build(
            plan,
            comps,
            title=str(draft.get("hook") or "Carousel") if isinstance(draft, dict) else "Carousel",
        )
        typo = _typography_from_context(context)
        typo_ids = tuple(str(a.get("asset_id")) for a in typo if a.get("asset_id"))
        profile_id = str(context.get("export_profile") or "linkedin")
        extra_safe = tuple(
            sa for c in comps for sa in c.safe_areas if isinstance(sa, dict)
        )
        definition = self._engine._definition.build(
            deck,
            draft_id=str(context.get("draft_id") or ""),
            typography_asset_ids=typo_ids,
            image_refs=tuple(str(x) for x in (context.get("image_refs") or ())),
            export_profile_id=profile_id,
            width=int(context.get("target_width") or 0) or None,
            height=int(context.get("target_height") or 0) or None,
            extra_safe_areas=extra_safe,
        )
        payload = {
            "carousel.deck": deck.to_dict(),
            "carousel.definition": definition.to_dict(),
        }
        context.update(payload)
        return NodeOutcome(success=True, outputs={"carousel.deck_id": deck.deck_id})


class CarouselOptimizeHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.carousel.domain.models import DeckDefinition

        definition = DeckDefinition.from_dict(context.get("carousel.definition") or {})
        result = self._engine._optimizer.optimize(definition)
        definition.optimization = result
        payload = {
            "carousel.definition": definition.to_dict(),
            "carousel.optimization": result.to_dict(),
        }
        context.update(payload)
        return NodeOutcome(
            success=True,
            outputs={"carousel.optimize": True, "composite": result.composite()},
        )


class CarouselRenderHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.carousel.domain.models import DeckDefinition

        deck = Deck.from_dict(context.get("carousel.deck") or {})
        definition = DeckDefinition.from_dict(context.get("carousel.definition") or {})
        if not definition.slides and deck.slides:
            definition = self._engine._definition.build(deck)
        profile_id = str(
            context.get("export_profile") or definition.export_profile_id or "linkedin"
        )
        render_plan = self._engine._render_planner.prepare(
            deck,
            width=definition.width,
            height=definition.height,
            export_profile_id=profile_id,
            definition=definition,
        )
        rendered = await self._engine._renderer.render(definition)
        payload = {
            "carousel.render_plan": render_plan.to_dict(),
            "carousel.rendered": rendered.to_dict(),
            "carousel.svgs": [s.svg for s in rendered.slides],
            "carousel.definition": definition.to_dict(),
        }
        self._engine._cache.render.put(deck.deck_id, rendered)
        context.update(payload)
        return NodeOutcome(
            success=True,
            outputs={
                "carousel.rendered_slides": len(rendered.slides),
                "editable_sot": "deck_definition",
            },
        )


class CarouselExportHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.carousel.domain.models import DeckDefinition

        deck = Deck.from_dict(context.get("carousel.deck") or {})
        rendered = self._engine._cache.render.get(deck.deck_id)
        if rendered is None:
            definition = DeckDefinition.from_dict(context.get("carousel.definition") or {})
            rendered = await self._engine._renderer.render(definition)
        formats = tuple(str(x) for x in (context.get("export_formats") or ("png", "pdf", "zip")))
        exports = await self._engine._export.export(rendered, formats=formats)
        payload = {"carousel.exports": [e.to_dict() for e in exports]}
        self._engine._cache.export.put(deck.deck_id, exports)
        context.update(payload)
        return NodeOutcome(success=True, outputs={"carousel.export_count": len(exports)})


class CarouselStoreHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        from app.modules.carousel.domain.models import (
            AssetDependencyGraph,
            CarouselAsset,
            DeckDefinition,
            DeckOptimizationResult,
            ExportArtifact,
            RenderedDeck,
        )

        deck = Deck.from_dict(context.get("carousel.deck") or {})
        rendered = self._engine._cache.render.get(deck.deck_id)
        exports_raw = context.get("carousel.exports") or []
        exports = tuple(
            ExportArtifact(
                artifact_id=str(x.get("artifact_id") or ""),
                format=str(x.get("format") or ""),
                object_key=str(x.get("object_key") or ""),
                size_bytes=int(x.get("size_bytes") or 0),
                slide_index=x.get("slide_index"),
                metadata=dict(x.get("metadata") or {}),
            )
            for x in exports_raw
            if isinstance(x, dict)
        )
        asset = CarouselAsset(
            asset_id=str(context.get("carousel.asset_id") or deck.deck_id),
            deck=deck,
            rendered=rendered if isinstance(rendered, RenderedDeck) else None,
            exports=exports,
            deck_definition=DeckDefinition.from_dict(context.get("carousel.definition")),
            optimization=DeckOptimizationResult.from_dict(context.get("carousel.optimization")),
            dependency_graph=AssetDependencyGraph.from_dict(
                context.get("carousel.dependency_graph")
            ),
            export_profile=str(context.get("export_profile") or "linkedin"),
            status="completed",
            metadata={"stored_via": "workflow"},
        )
        stored = await self._engine._store.store(asset)
        payload = {"carousel.stored": True, "carousel.asset_id": stored.asset_id}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class CarouselPipelineHandler(_Base):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        draft = _draft_from_context(context)
        req = CarouselPipelineRequest(
            organization_id=str(context.get("organization_id") or "org"),
            draft_id=str(context.get("draft_id") or "draft"),
            draft_snapshot=draft if isinstance(draft, dict) else {},
            typography_assets=_typography_from_context(context),
            image_refs=tuple(str(x) for x in (context.get("image_refs") or ())),
            target_width=int(context.get("target_width") or 1080),
            target_height=int(context.get("target_height") or 1350),
            export_profile=str(context.get("export_profile") or "linkedin"),
            use_mock_renderer=True,
        )
        result = await self._engine.run(req)
        payload = {"carousel.result": result.to_dict(), "carousel.status": result.status}
        context.update(payload)
        return NodeOutcome(success=result.status == "completed", outputs=payload)


def register_carousel_handlers(node_registry, engine=None) -> None:
    eng = engine or CarouselFactory.create_memory()
    node_registry.register("carousel.plan", CarouselPlanHandler(eng))
    node_registry.register("carousel.compose", CarouselComposeHandler(eng))
    node_registry.register("carousel.build", CarouselBuildHandler(eng))
    node_registry.register("carousel.optimize", CarouselOptimizeHandler(eng))
    node_registry.register("carousel.render", CarouselRenderHandler(eng))
    node_registry.register("carousel.export", CarouselExportHandler(eng))
    node_registry.register("carousel.store", CarouselStoreHandler(eng))
    node_registry.register("carousel.pipeline", CarouselPipelineHandler(eng))
