"""Workflow node handlers for Visual Intelligence Engine."""

from __future__ import annotations

from typing import Any

from app.modules.image.application.factory import VisualIntelligenceFactory
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    ImagePromptRequest,
    ImagePipelineRequest,
)
from app.modules.workflow.domain.models import NodeOutcome, WorkflowContext, WorkflowNode


class _BaseImageHandler:
    def __init__(self, engine=None) -> None:
        self._engine = engine or VisualIntelligenceFactory.create_memory()


class VisualBriefHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        draft = context.get("content.draft") or context.get("image.draft") or {}
        plan = context.get("content.plan") or context.get("image.content_plan") or {}
        if not isinstance(draft, dict):
            return NodeOutcome(success=False, outputs={}, error_message="missing draft")
        brief = self._engine.enrich_brief(draft, plan if isinstance(plan, dict) else None)
        payload = {"image.brief": brief}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class VisualSceneHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        brief = context.get("image.brief") or {}
        plan = context.get("content.plan") or {}
        scene = self._engine.plan_scene(brief if isinstance(brief, dict) else {}, plan if isinstance(plan, dict) else None)
        payload = {"image.scene": scene}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class VisualComposeHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        brief = context.get("image.brief") or {}
        scene = context.get("image.scene") or {}
        composition = self._engine.plan_composition(
            brief if isinstance(brief, dict) else {},
            scene if isinstance(scene, dict) else {},
        )
        payload = {"image.composition": composition}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ImagePromptHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        try:
            prompt = self._engine.build_prompt(
                context.get("image.brief") or {},
                context.get("image.scene") or {},
                context.get("image.composition") or {},
                context.get("image.brand") if isinstance(context.get("image.brand"), dict) else None,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeOutcome(success=False, outputs={}, error_message=str(exc))
        payload = {"image.prompt_request": prompt}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ImageGenerateHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        raw = context.get("image.prompt_request")
        if not isinstance(raw, dict):
            return NodeOutcome(success=False, outputs={}, error_message="missing prompt_request")
        pr = ImagePromptRequest.from_dict(raw)
        if self._engine._orch is None:
            return NodeOutcome(success=False, outputs={}, error_message="orchestrator missing")
        result = await self._engine._orch.execute(pr)
        meta = {
            "provider": result.provider,
            "model": result.model,
            "width": result.width,
            "height": result.height,
            "latency_ms": result.latency_ms,
            "workflow_id": result.workflow_id,
            "workflow_version": result.workflow_version,
        }
        payload = {"image.generation": meta, "image.bytes": result.image_bytes}
        context.update(payload)
        return NodeOutcome(success=True, outputs={"image.generation": meta})


class ImageValidateHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        data = context.get("image.bytes")
        if not data:
            return NodeOutcome(success=False, outputs={}, error_message="missing image bytes")
        brief = EnrichedVisualBrief.from_dict(context.get("image.brief") or {})
        composition = CompositionPlan.from_dict(context.get("image.composition") or {})
        validation = self._engine._validator.validate(
            data, composition=composition, brief=brief, brand=context.get("image.brand") or {}
        )
        payload = {"image.validation": validation.to_dict(), "image.validation_passed": validation.passed}
        context.update(payload)
        if not validation.passed:
            return NodeOutcome(success=False, outputs=payload, error_message="validation failed")
        return NodeOutcome(success=True, outputs=payload)


class ImageOptimizeHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        data = context.get("image.bytes")
        if not data:
            return NodeOutcome(success=False, outputs={}, error_message="missing image bytes")
        gen = context.get("image.generation") or {}
        composition = CompositionPlan.from_dict(context.get("image.composition") or {})
        bundle = self._engine._optimizer.optimize(
            data,
            width=int(gen.get("width") or composition.width),
            height=int(gen.get("height") or composition.height),
        )
        payload = {
            "image.optimized": True,
            "image.formats": list(bundle.formats.keys()),
            "image.bundle": bundle,
        }
        context.update(payload)
        return NodeOutcome(
            success=True,
            outputs={"image.optimized": True, "image.formats": list(bundle.formats.keys())},
        )


class ImageStoreHandler(_BaseImageHandler):
    def __init__(self, engine=None) -> None:
        # Durable store — local disk via STORAGE_PROVIDER
        self._engine = engine or VisualIntelligenceFactory.create()

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        bundle = context.get("image.bundle")
        if bundle is None:
            return NodeOutcome(success=False, outputs={}, error_message="missing optimized bundle")
        org = str(context.get("organization_id") or "org")
        draft_id = str(context.get("draft_id") or context.get("image.draft_id") or "draft")
        job_id = str(context.get("image.job_id") or "job")
        assets = await self._engine._assets.store(
            organization_id=org,
            job_id=job_id,
            draft_id=draft_id,
            bundle=bundle,
            metadata={"source": "workflow"},
        )
        payload = {"image.assets": [a.to_dict() for a in assets], "image.stored": True}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ImagePipelineHandler(_BaseImageHandler):
    """Single-node convenience: full Visual Intelligence run."""

    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        draft = context.get("content.draft") or context.get("image.draft") or {}
        if not isinstance(draft, dict):
            return NodeOutcome(success=False, outputs={}, error_message="missing draft")
        req = ImagePipelineRequest(
            organization_id=str(context.get("organization_id") or "org"),
            draft_id=str(context.get("draft_id") or draft.get("id") or "draft"),
            draft=draft,
            content_plan=context.get("content.plan") if isinstance(context.get("content.plan"), dict) else {},
            brand=context.get("image.brand") if isinstance(context.get("image.brand"), dict) else {},
            correlation_id=str(context.get("correlation_id") or ""),
        )
        result = await self._engine.run(req)
        payload = {"image.result": result.to_dict(), "image.status": result.status}
        context.update(payload)
        ok = result.status == "completed"
        return NodeOutcome(success=ok, outputs=payload, error_message=None if ok else result.status)


class VisualLayoutHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        gen = context.get("image.generation") or {}
        layout = self._engine.plan_layout(
            context.get("image.brief") or {},
            context.get("image.scene") or {},
            context.get("image.composition") or {},
            image_width=int(gen.get("width") or 1080),
            image_height=int(gen.get("height") or 1350),
        )
        payload = {"image.layout": layout}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ImageAnalyzeHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        data = context.get("image.bytes")
        if not data:
            return NodeOutcome(success=False, outputs={}, error_message="missing image bytes")
        from app.modules.image.domain.models import LayoutPlan, ScenePlan

        report = self._engine._analyzer.analyze(
            data,
            scene=ScenePlan.from_dict(context.get("image.scene") or {}),
            brief=EnrichedVisualBrief.from_dict(context.get("image.brief") or {}),
            layout=LayoutPlan.from_dict(context.get("image.layout") or {}),
            brand=context.get("image.brand") if isinstance(context.get("image.brand"), dict) else None,
        )
        payload = {"image.asset_intelligence": report.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs=payload)


class ImageEmbedHandler(_BaseImageHandler):
    async def execute(self, node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        data = context.get("image.bytes")
        if not data:
            return NodeOutcome(success=False, outputs={}, error_message="missing image bytes")
        job_id = str(context.get("image.job_id") or context.get("job_id") or "job")
        org = str(context.get("organization_id") or "org")
        emb = self._engine._embeddings.embed_image(
            data, job_id=job_id, organization_id=org
        )
        payload = {"image.embedding": emb.to_dict()}
        context.update(payload)
        return NodeOutcome(success=True, outputs={"image.embedding": {k: v for k, v in emb.to_dict().items() if k != "vector"} | {"dimensions": emb.dimensions}})


def register_image_handlers(node_registry, engine=None) -> None:
    eng = engine or VisualIntelligenceFactory.create_memory()
    node_registry.register("visual.brief", VisualBriefHandler(eng))
    node_registry.register("visual.scene", VisualSceneHandler(eng))
    node_registry.register("visual.compose", VisualComposeHandler(eng))
    node_registry.register("visual.layout", VisualLayoutHandler(eng))
    node_registry.register("image.prompt", ImagePromptHandler(eng))
    node_registry.register("image.generate", ImageGenerateHandler(eng))
    node_registry.register("image.validate", ImageValidateHandler(eng))
    node_registry.register("image.analyze", ImageAnalyzeHandler(eng))
    node_registry.register("image.embed", ImageEmbedHandler(eng))
    node_registry.register("image.optimize", ImageOptimizeHandler(eng))
    node_registry.register("image.store", ImageStoreHandler(eng))
    node_registry.register("image.pipeline", ImagePipelineHandler(eng))
