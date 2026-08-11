"""Visual Intelligence Engine facade — M10 + refinements (no typography)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.image.application.asset_intelligence import DefaultAssetAnalyzer
from app.modules.image.application.assets import MemoryImageAssetStore
from app.modules.image.application.brief import DefaultVisualBriefEnricher
from app.modules.image.application.cache import InMemoryImagePromptCache
from app.modules.image.application.composition import DefaultCompositionPlanner
from app.modules.image.application.embeddings import DefaultVisualEmbeddingService
from app.modules.image.application.layout import DefaultLayoutPlanner
from app.modules.image.application.metrics import ImageMetricsSnapshot, InMemoryImageMetrics
from app.modules.image.application.optimizer import DefaultImageOptimizer
from app.modules.image.application.policy import DefaultVisualPolicyEngine
from app.modules.image.application.prompt_builder import DefaultImagePromptBuilder
from app.modules.image.application.replay import DefaultImageDiffService, InMemoryImageReplayStore
from app.modules.image.application.scene import DefaultScenePlanner
from app.modules.image.application.validator import DefaultImageValidator
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    ImagePipelineRequest,
    ImagePipelineResult,
    ImagePromptRequest,
    ImageReplayRecord,
    ImageValidationResult,
    ScenePlan,
    new_job_id,
)
from app.modules.image.domain.ports import (
    AssetAnalyzer,
    CompositionPlanner,
    ImageAssetStore,
    ImageOrchestrator,
    ImageOptimizer,
    ImagePromptBuilder,
    ImageValidator,
    LayoutPlanner,
    ScenePlanner,
    VisualBriefEnricher,
    VisualEmbeddingService,
    VisualPolicyEngine,
)

logger = get_logger(__name__)


class DefaultVisualIntelligenceEngine:
    def __init__(
        self,
        *,
        brief_enricher: VisualBriefEnricher | None = None,
        scene_planner: ScenePlanner | None = None,
        composition_planner: CompositionPlanner | None = None,
        policy_engine: VisualPolicyEngine | None = None,
        prompt_builder: ImagePromptBuilder | None = None,
        orchestrator: ImageOrchestrator | None = None,
        validator: ImageValidator | None = None,
        optimizer: ImageOptimizer | None = None,
        asset_store: ImageAssetStore | None = None,
        layout_planner: LayoutPlanner | None = None,
        asset_analyzer: AssetAnalyzer | None = None,
        embedding_service: VisualEmbeddingService | None = None,
        prompt_cache: InMemoryImagePromptCache | None = None,
        replay_store: InMemoryImageReplayStore | None = None,
        metrics: InMemoryImageMetrics | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self._brief = brief_enricher or DefaultVisualBriefEnricher(config_dir)
        self._scene = scene_planner or DefaultScenePlanner(config_dir)
        self._compose = composition_planner or DefaultCompositionPlanner(config_dir)
        self._policy = policy_engine or DefaultVisualPolicyEngine(config_dir)
        self._prompts = prompt_builder or DefaultImagePromptBuilder(config_dir)
        self._orch = orchestrator
        self._validator = validator or DefaultImageValidator(config_dir)
        self._optimizer = optimizer or DefaultImageOptimizer(config_dir)
        self._assets = asset_store or MemoryImageAssetStore()
        self._layout = layout_planner or DefaultLayoutPlanner(config_dir)
        self._analyzer = asset_analyzer or DefaultAssetAnalyzer()
        self._embeddings = embedding_service or DefaultVisualEmbeddingService(config_dir=config_dir)
        self._prompt_cache = prompt_cache or InMemoryImagePromptCache()
        self._replay = replay_store or InMemoryImageReplayStore()
        self._diff = DefaultImageDiffService()
        self._metrics = metrics or InMemoryImageMetrics()

    @property
    def replay_store(self) -> InMemoryImageReplayStore:
        return self._replay

    @property
    def diff_service(self) -> DefaultImageDiffService:
        return self._diff

    @property
    def embedding_service(self) -> VisualEmbeddingService:
        return self._embeddings

    async def run(self, request: ImagePipelineRequest) -> ImagePipelineResult:
        if self._orch is None:
            raise AppError("ImageOrchestrator is required")

        job_id = new_job_id()
        draft = request.draft
        brief = self._brief.enrich(
            draft,
            content_plan=request.content_plan,
            existing_brief=(
                draft.get("visual_brief") if isinstance(draft.get("visual_brief"), dict) else None
            ),
        )
        scene = self._scene.plan(brief, content_plan=request.content_plan)
        composition = self._compose.plan(brief, scene)
        policy = self._policy.validate(brief, scene, composition, brand=request.brand)
        if not policy.passed:
            return ImagePipelineResult(
                job_id=job_id,
                status="policy_rejected",
                brief=brief,
                scene=scene,
                composition=composition,
                policy=policy,
                prompt_request=self._prompts.build(brief, scene, composition, brand=request.brand),
                validation=ImageValidationResult(passed=False, score=0.0, reason_codes=("policy_rejected",)),
                metadata={"reason_codes": list(policy.reason_codes)},
            )

        prompt_req = self._prompts.build(
            brief,
            scene,
            composition,
            brand=request.brand,
            workflow_id=request.preferred_workflow_id,
            variant_index=request.variant_index,
            seed_override=request.seed_override,
        )
        ph = prompt_req.prompt_hash()
        cached = self._prompt_cache.get(ph)
        if cached is None:
            self._prompt_cache.put(ph, prompt_req)
        else:
            # Preserve seed from built request if cache lacked it
            if cached.seed is None:
                cached.seed = prompt_req.seed
            prompt_req = cached

        return await self._finish_from_prompt(
            request=request,
            job_id=job_id,
            brief=brief,
            scene=scene,
            composition=composition,
            policy=policy,
            prompt_req=prompt_req,
            prompt_hash=ph,
            replay_of=request.replay_of_job_id,
        )

    async def replay(
        self, replay_id: str | None = None, *, job_id: str | None = None
    ) -> ImagePipelineResult:
        if self._orch is None:
            raise AppError("ImageOrchestrator is required")
        record = None
        if replay_id:
            record = self._replay.get(replay_id)
        elif job_id:
            record = self._replay.get_by_job(job_id)
        if record is None:
            raise NotFoundError("ImageReplay", replay_id or job_id or "")

        brief = EnrichedVisualBrief.from_dict(record.visual_brief)
        scene = ScenePlan.from_dict(record.scene)
        composition = CompositionPlan.from_dict(record.composition)
        prompt_req = ImagePromptRequest.from_dict(record.prompt_request)
        if record.seed is not None:
            prompt_req.seed = record.seed
        prompt_req.workflow_id = record.workflow_id or prompt_req.workflow_id
        prompt_req.workflow_version = record.workflow_version or prompt_req.workflow_version

        org = str((record.result_metadata or {}).get("organization_id") or "org")
        draft_id = str((record.result_metadata or {}).get("draft_id") or "draft")
        request = ImagePipelineRequest(
            organization_id=org,
            draft_id=draft_id,
            draft={"visual_brief": record.visual_brief},
            brand=dict((record.result_metadata or {}).get("brand") or {}),
            replay_of_job_id=record.job_id,
        )
        policy = self._policy.validate(brief, scene, composition, brand=request.brand)
        return await self._finish_from_prompt(
            request=request,
            job_id=new_job_id(),
            brief=brief,
            scene=scene,
            composition=composition,
            policy=policy,
            prompt_req=prompt_req,
            prompt_hash=prompt_req.prompt_hash(),
            replay_of=record.job_id,
        )

    async def _finish_from_prompt(
        self,
        *,
        request: ImagePipelineRequest,
        job_id: str,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        policy: Any,
        prompt_req: ImagePromptRequest,
        prompt_hash: str,
        replay_of: str | None,
    ) -> ImagePipelineResult:
        gen = await self._orch.execute(prompt_req)  # type: ignore[union-attr]
        validation = self._validator.validate(
            gen.image_bytes,
            composition=composition,
            brief=brief,
            brand=request.brand,
        )
        quality = validation.breakdown
        quality_score = validation.score

        if not validation.passed:
            return ImagePipelineResult(
                job_id=job_id,
                status="validation_failed",
                brief=brief,
                scene=scene,
                composition=composition,
                policy=policy,
                prompt_request=prompt_req,
                validation=validation,
                quality=quality,
                provider=gen.provider,
                model=gen.model,
                quality_score=quality_score,
                latency_ms=gen.latency_ms,
                cost_estimate=gen.cost_estimate,
                queue_time_ms=int(gen.metadata.get("queue_time_ms") or 0),
                retry_count=int(gen.metadata.get("retry_count") or 0),
                prompt_hash=prompt_hash,
                workflow_id=gen.workflow_id or prompt_req.workflow_id,
                workflow_version=gen.workflow_version or prompt_req.workflow_version,
                seed=prompt_req.seed,
                metadata={"reason_codes": list(validation.reason_codes)},
            )

        layout = self._layout.plan(
            brief=brief,
            scene=scene,
            composition=composition,
            image_width=gen.width,
            image_height=gen.height,
        )
        intelligence = self._analyzer.analyze(
            gen.image_bytes,
            scene=scene,
            brief=brief,
            layout=layout,
            brand=request.brand,
        )
        embedding = self._embeddings.embed_image(
            gen.image_bytes,
            job_id=job_id,
            organization_id=request.organization_id,
        )

        bundle = self._optimizer.optimize(gen.image_bytes, width=gen.width, height=gen.height)
        assets = await self._assets.store(
            organization_id=request.organization_id,
            job_id=job_id,
            draft_id=request.draft_id,
            bundle=bundle,
            metadata={
                "prompt_hash": prompt_hash,
                "provider": gen.provider,
                "model": gen.model,
                "workflow_id": gen.workflow_id or prompt_req.workflow_id,
                "workflow_version": gen.workflow_version or prompt_req.workflow_version,
                "correlation_id": request.correlation_id,
                "quality_score": quality_score,
                "layout_plan": layout.to_dict(),
                "asset_intelligence": intelligence.to_dict(),
                "seed": prompt_req.seed,
            },
        )
        if assets:
            embedding.asset_id = assets[0].asset_id

        result = ImagePipelineResult(
            job_id=job_id,
            status="completed",
            brief=brief,
            scene=scene,
            composition=composition,
            policy=policy,
            prompt_request=prompt_req,
            validation=validation,
            assets=assets,
            layout=layout,
            asset_intelligence=intelligence,
            embedding=embedding,
            quality=quality,
            provider=gen.provider,
            model=gen.model,
            quality_score=quality_score,
            latency_ms=gen.latency_ms,
            cost_estimate=gen.cost_estimate,
            queue_time_ms=int(gen.metadata.get("queue_time_ms") or 0),
            retry_count=int(gen.metadata.get("retry_count") or 0),
            prompt_hash=prompt_hash,
            workflow_id=gen.workflow_id or prompt_req.workflow_id,
            workflow_version=gen.workflow_version or prompt_req.workflow_version,
            seed=prompt_req.seed,
            metadata={
                "replay_of_job_id": replay_of,
                "formats": list(bundle.formats.keys()),
                "layout_plan": layout.to_dict(),
                "cost_estimate": gen.cost_estimate,
            },
        )
        self._replay.save(
            ImageReplayRecord(
                replay_id=str(uuid.uuid4()),
                job_id=job_id,
                prompt_request=prompt_req.to_dict(),
                scene=scene.to_dict(),
                composition=composition.to_dict(),
                provider=gen.provider,
                workflow_id=result.workflow_id,
                workflow_version=result.workflow_version,
                visual_brief=brief.to_dict(),
                layout=layout.to_dict(),
                seed=prompt_req.seed,
                asset_refs=tuple(a.to_dict() for a in assets),
                quality_breakdown=quality.to_dict() if quality else {},
                result_metadata={
                    "quality_score": quality_score,
                    "organization_id": request.organization_id,
                    "draft_id": request.draft_id,
                    "brand": request.brand,
                    "replay_of_job_id": replay_of,
                },
            )
        )
        self._metrics.record(
            ImageMetricsSnapshot(
                generation_time_ms=gen.latency_ms,
                queue_time_ms=result.queue_time_ms,
                retries=result.retry_count,
                image_quality=quality_score,
                validation_results=validation.to_dict(),
                provider_usage={gen.provider: 1},
                workflow_version=f"{result.workflow_id}@{result.workflow_version}",
            )
        )
        logger.info(
            "visual_intelligence_completed",
            extra={"job_id": job_id, "provider": gen.provider, "quality": quality_score},
        )
        return result

    def enrich_brief(self, draft: dict[str, Any], content_plan: dict | None = None) -> dict:
        return self._brief.enrich(draft, content_plan=content_plan).to_dict()

    def plan_scene(self, brief: dict[str, Any], content_plan: dict | None = None) -> dict:
        b = EnrichedVisualBrief.from_dict(brief)
        return self._scene.plan(b, content_plan=content_plan).to_dict()

    def plan_composition(self, brief: dict[str, Any], scene: dict[str, Any]) -> dict:
        return self._compose.plan(
            EnrichedVisualBrief.from_dict(brief), ScenePlan.from_dict(scene)
        ).to_dict()

    def plan_layout(
        self,
        brief: dict[str, Any],
        scene: dict[str, Any],
        composition: dict[str, Any],
        *,
        image_width: int = 1080,
        image_height: int = 1350,
    ) -> dict:
        return self._layout.plan(
            brief=EnrichedVisualBrief.from_dict(brief),
            scene=ScenePlan.from_dict(scene),
            composition=CompositionPlan.from_dict(composition),
            image_width=image_width,
            image_height=image_height,
        ).to_dict()

    def build_prompt(
        self,
        brief: dict[str, Any],
        scene: dict[str, Any],
        composition: dict[str, Any],
        brand: dict | None = None,
    ) -> dict:
        b = EnrichedVisualBrief.from_dict(brief)
        s = ScenePlan.from_dict(scene)
        c = CompositionPlan.from_dict(composition)
        policy = self._policy.validate(b, s, c, brand=brand)
        if not policy.passed:
            raise ValidationError(f"Visual policy failed: {list(policy.reason_codes)}")
        return self._prompts.build(b, s, c, brand=brand).to_dict()
