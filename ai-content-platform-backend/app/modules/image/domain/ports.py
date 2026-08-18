"""Image module ports — generation, quality check, prompt enhancement."""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.image.domain.models import (
    AssetIntelligenceReport,
    CompositionPlan,
    EnrichedVisualBrief,
    ImageAssetRecord,
    ImageDiff,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImagePipelineRequest,
    ImagePipelineResult,
    ImagePromptRequest,
    ImageReplayRecord,
    ImageValidationResult,
    LayoutPlan,
    OptimizedImageBundle,
    ScenePlan,
    VisualEmbedding,
    VisualPolicyResult,
    WorkflowDescriptor,
)

__all__ = [
    "ImageGenerationRequest",
    "ImageGenerationResult",
    "ImageGenerator",
    "ImageProvider",
    "PromptEnhancer",
    "QualityChecker",
    "VisualBriefEnricher",
    "ScenePlanner",
    "CompositionPlanner",
    "VisualPolicyEngine",
    "ImagePromptBuilder",
    "ImageOrchestrator",
    "ImageValidator",
    "ImageOptimizer",
    "ImageAssetStore",
    "ComfyWorkflowRegistry",
    "ImagePromptCache",
    "ImageReplayStore",
    "ImageDiffService",
    "VisualIntelligenceEngine",
]


class VisualBriefEnricher(Protocol):
    def enrich(
        self,
        draft: dict[str, Any],
        *,
        content_plan: dict[str, Any] | None = None,
        existing_brief: dict[str, Any] | None = None,
    ) -> EnrichedVisualBrief: ...


class ScenePlanner(Protocol):
    def plan(self, brief: EnrichedVisualBrief, *, content_plan: dict[str, Any] | None = None) -> ScenePlan: ...


class CompositionPlanner(Protocol):
    def plan(self, brief: EnrichedVisualBrief, scene: ScenePlan) -> CompositionPlan: ...


class VisualPolicyEngine(Protocol):
    def validate(
        self,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        *,
        brand: dict[str, Any] | None = None,
    ) -> VisualPolicyResult: ...


class ImagePromptBuilder(Protocol):
    def build(
        self,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        *,
        brand: dict[str, Any] | None = None,
        workflow_id: str | None = None,
    ) -> ImagePromptRequest: ...


class ImageProvider(Protocol):
    """Port for pixel generation — cloud or ComfyUI adapters."""

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...


ImageGenerator = ImageProvider


class PromptEnhancer(Protocol):
    async def enhance(self, raw_prompt: str, brand_context: dict) -> str: ...


class QualityChecker(Protocol):
    async def check(self, image_bytes: bytes) -> float: ...


class ImageOrchestrator(Protocol):
    async def execute(
        self, prompt_request: ImagePromptRequest, *, logo_bytes: bytes | None = None
    ) -> ImageGenerationResult: ...


class ImageValidator(Protocol):
    def validate(
        self,
        image_bytes: bytes,
        *,
        composition: CompositionPlan,
        brief: EnrichedVisualBrief,
        brand: dict[str, Any] | None = None,
    ) -> ImageValidationResult: ...


class ImageOptimizer(Protocol):
    def optimize(self, image_bytes: bytes, *, width: int, height: int) -> OptimizedImageBundle: ...


class ImageAssetStore(Protocol):
    async def store(
        self,
        *,
        organization_id: str,
        job_id: str,
        draft_id: str,
        bundle: OptimizedImageBundle,
        metadata: dict[str, Any],
    ) -> tuple[ImageAssetRecord, ...]: ...


class ComfyWorkflowRegistry(Protocol):
    def get(self, workflow_id: str, version: str | None = None) -> WorkflowDescriptor: ...

    def load_graph(self, descriptor: WorkflowDescriptor) -> dict[str, Any]: ...

    def list_workflows(self) -> list[WorkflowDescriptor]: ...

    def render_graph(self, descriptor: WorkflowDescriptor, params: dict[str, Any]) -> dict[str, Any]: ...


class ImagePromptCache(Protocol):
    def get(self, prompt_hash: str) -> ImagePromptRequest | None: ...

    def put(self, prompt_hash: str, request: ImagePromptRequest) -> None: ...


class ImageReplayStore(Protocol):
    def save(self, record: ImageReplayRecord) -> None: ...

    def get(self, replay_id: str) -> ImageReplayRecord | None: ...

    def get_by_job(self, job_id: str) -> ImageReplayRecord | None: ...


class LayoutPlanner(Protocol):
    def plan(
        self,
        *,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        image_width: int,
        image_height: int,
    ) -> LayoutPlan: ...


class AssetAnalyzer(Protocol):
    def analyze(
        self,
        image_bytes: bytes,
        *,
        scene: ScenePlan,
        brief: EnrichedVisualBrief,
        layout: LayoutPlan | None = None,
        brand: dict[str, Any] | None = None,
    ) -> AssetIntelligenceReport: ...


class VisualEmbeddingService(Protocol):
    def embed_image(
        self,
        image_bytes: bytes,
        *,
        job_id: str,
        organization_id: str,
        asset_id: str = "",
    ) -> VisualEmbedding: ...

    def similar(self, job_id: str, *, top_k: int | None = None) -> list[tuple[str, float]]: ...

    def duplicates(self, job_id: str) -> list[tuple[str, float]]: ...

    def recommend(self, job_id: str, *, top_k: int | None = None) -> list[tuple[str, float]]: ...


class ImageDiffService(Protocol):
    def diff(self, left: ImagePipelineResult, right: ImagePipelineResult) -> ImageDiff: ...


class VisualIntelligenceEngine(Protocol):
    async def run(self, request: ImagePipelineRequest) -> ImagePipelineResult: ...

    async def replay(self, replay_id: str | None = None, *, job_id: str | None = None) -> ImagePipelineResult: ...
