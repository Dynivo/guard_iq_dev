"""Visual Intelligence Engine domain models (M10)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ImageArtifactRole(str, Enum):
    ORIGINAL = "original"
    OPTIMIZED = "optimized"
    THUMBNAIL = "thumbnail"


@dataclass(slots=True)
class EnrichedVisualBrief:
    """Normalized brief for M10 — never contains pixels."""

    illustration_style: str = ""
    theme: str = ""
    purpose: str = ""
    audience: str = ""
    visual_tone: str = ""
    icons: tuple[str, ...] = ()
    infographic_suggestions: tuple[str, ...] = ()
    typography_safe_area: str = ""
    negative_prompt: str = ""
    color_palette: tuple[str, ...] = ()
    brand_direction: str = ""
    image_intent: str = ""
    scene_hint: str = ""
    composition_hint: str = ""
    focal_point: str = ""
    camera_angle: str = ""
    visual_hierarchy: str = ""
    emotion: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "illustration_style": self.illustration_style,
            "theme": self.theme,
            "purpose": self.purpose,
            "audience": self.audience,
            "visual_tone": self.visual_tone,
            "icons": list(self.icons),
            "infographic_suggestions": list(self.infographic_suggestions),
            "typography_safe_area": self.typography_safe_area,
            "negative_prompt": self.negative_prompt,
            "color_palette": list(self.color_palette),
            "brand_direction": self.brand_direction,
            "image_intent": self.image_intent,
            "scene_hint": self.scene_hint,
            "composition_hint": self.composition_hint,
            "focal_point": self.focal_point,
            "camera_angle": self.camera_angle,
            "visual_hierarchy": self.visual_hierarchy,
            "emotion": self.emotion,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> EnrichedVisualBrief:
        if not data:
            return EnrichedVisualBrief()
        icons = data.get("icons") or data.get("icon_suggestions") or ()
        infos = data.get("infographic_suggestions") or ()
        palette = data.get("color_palette") or ()
        return EnrichedVisualBrief(
            illustration_style=str(data.get("illustration_style") or ""),
            theme=str(data.get("theme") or ""),
            purpose=str(data.get("purpose") or ""),
            audience=str(data.get("audience") or ""),
            visual_tone=str(data.get("visual_tone") or data.get("emotion") or ""),
            icons=tuple(str(i) for i in icons),
            infographic_suggestions=tuple(str(i) for i in infos),
            typography_safe_area=str(data.get("typography_safe_area") or ""),
            negative_prompt=str(data.get("negative_prompt") or ""),
            color_palette=tuple(str(c) for c in palette),
            brand_direction=str(data.get("brand_direction") or ""),
            image_intent=str(data.get("image_intent") or data.get("visual_intent") or ""),
            scene_hint=str(data.get("scene_hint") or data.get("scene") or ""),
            composition_hint=str(data.get("composition_hint") or data.get("composition") or ""),
            focal_point=str(data.get("focal_point") or ""),
            camera_angle=str(data.get("camera_angle") or ""),
            visual_hierarchy=str(data.get("visual_hierarchy") or ""),
            emotion=str(data.get("emotion") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ScenePlan:
    layout: str = "centered"
    foreground: tuple[str, ...] = ()
    background: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    people: tuple[str, ...] = ()
    icons: tuple[str, ...] = ()
    graphs: tuple[str, ...] = ()
    charts: tuple[str, ...] = ()
    white_space: str = "balanced"
    reading_direction: str = "ltr_top_to_bottom"
    visual_hierarchy: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "foreground": list(self.foreground),
            "background": list(self.background),
            "objects": list(self.objects),
            "people": list(self.people),
            "icons": list(self.icons),
            "graphs": list(self.graphs),
            "charts": list(self.charts),
            "white_space": self.white_space,
            "reading_direction": self.reading_direction,
            "visual_hierarchy": self.visual_hierarchy,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> ScenePlan:
        if not data:
            return ScenePlan()

        def _t(key: str) -> tuple[str, ...]:
            return tuple(str(x) for x in (data.get(key) or ()))

        return ScenePlan(
            layout=str(data.get("layout") or "centered"),
            foreground=_t("foreground"),
            background=_t("background"),
            objects=_t("objects"),
            people=_t("people"),
            icons=_t("icons"),
            graphs=_t("graphs"),
            charts=_t("charts"),
            white_space=str(data.get("white_space") or "balanced"),
            reading_direction=str(data.get("reading_direction") or "ltr_top_to_bottom"),
            visual_hierarchy=str(data.get("visual_hierarchy") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class CompositionPlan:
    camera: str = "eye_level"
    perspective: str = "mild_depth"
    balance: str = "rule_of_thirds"
    spacing: str = "generous"
    aspect_ratio: str = "4:5"
    width: int = 1080
    height: int = 1350
    focus: str = "center_subject"
    contrast: str = "moderate"
    depth: str = "layered"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera": self.camera,
            "perspective": self.perspective,
            "balance": self.balance,
            "spacing": self.spacing,
            "aspect_ratio": self.aspect_ratio,
            "width": self.width,
            "height": self.height,
            "focus": self.focus,
            "contrast": self.contrast,
            "depth": self.depth,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> CompositionPlan:
        if not data:
            return CompositionPlan()
        return CompositionPlan(
            camera=str(data.get("camera") or "eye_level"),
            perspective=str(data.get("perspective") or "mild_depth"),
            balance=str(data.get("balance") or "rule_of_thirds"),
            spacing=str(data.get("spacing") or "generous"),
            aspect_ratio=str(data.get("aspect_ratio") or "4:5"),
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            focus=str(data.get("focus") or "center_subject"),
            contrast=str(data.get("contrast") or "moderate"),
            depth=str(data.get("depth") or "layered"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class VisualPolicyResult:
    passed: bool = True
    brand_colors_ok: bool = True
    restricted_elements_ok: bool = True
    forbidden_symbols_ok: bool = True
    unsafe_content_ok: bool = True
    compliance_ok: bool = True
    logo_usage_ok: bool = True
    typography_safe_area_ok: bool = True
    image_size_ok: bool = True
    reason_codes: tuple[str, ...] = ()
    score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "brand_colors_ok": self.brand_colors_ok,
            "restricted_elements_ok": self.restricted_elements_ok,
            "forbidden_symbols_ok": self.forbidden_symbols_ok,
            "unsafe_content_ok": self.unsafe_content_ok,
            "compliance_ok": self.compliance_ok,
            "logo_usage_ok": self.logo_usage_ok,
            "typography_safe_area_ok": self.typography_safe_area_ok,
            "image_size_ok": self.image_size_ok,
            "reason_codes": list(self.reason_codes),
            "score": self.score,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ImagePromptRequest:
    """Provider-agnostic prompt package — never calls providers."""

    positive_prompt: str
    negative_prompt: str = ""
    width: int = 1080
    height: int = 1350
    style: str = "professional"
    workflow_id: str = "flux_dev"
    workflow_version: str = "1"
    seed: int | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "style": self.style,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "seed": self.seed,
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
        }

    def prompt_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> ImagePromptRequest:
        if not data:
            return ImagePromptRequest(positive_prompt="")
        return ImagePromptRequest(
            positive_prompt=str(data.get("positive_prompt") or ""),
            negative_prompt=str(data.get("negative_prompt") or ""),
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            style=str(data.get("style") or "professional"),
            workflow_id=str(data.get("workflow_id") or "flux_dev"),
            workflow_version=str(data.get("workflow_version") or "1"),
            seed=data.get("seed"),
            parameters=dict(data.get("parameters") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ImageGenerationRequest:
    prompt: str
    width: int = 1080
    height: int = 1350
    style: str = "professional"
    negative_prompt: str = ""
    workflow_id: str = "flux_dev"
    workflow_version: str = "1"
    seed: int | None = None
    parameters: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    # Raw brand logo bytes for providers that support image-reference input
    # (OpenAI images.edit, Gemini multi-part generateContent). Deliberately kept
    # off ImagePromptRequest — that object is hashed/cached/replayed as JSON and
    # must never carry binary payloads.
    logo_bytes: bytes | None = None

    @classmethod
    def from_prompt_request(
        cls, req: ImagePromptRequest, *, logo_bytes: bytes | None = None
    ) -> ImageGenerationRequest:
        return cls(
            prompt=req.positive_prompt,
            width=req.width,
            height=req.height,
            style=req.style,
            negative_prompt=req.negative_prompt,
            workflow_id=req.workflow_id,
            workflow_version=req.workflow_version,
            seed=req.seed,
            parameters=dict(req.parameters),
            metadata=dict(req.metadata),
            logo_bytes=logo_bytes,
        )


@dataclass(slots=True)
class ImageGenerationResult:
    image_bytes: bytes
    width: int
    height: int
    provider: str
    model: str
    latency_ms: int
    cost_estimate: float | None = None
    workflow_id: str = ""
    workflow_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VisualQualityBreakdown:
    composition: float = 0.0
    contrast: float = 0.0
    brand_alignment: float = 0.0
    whitespace: float = 0.0
    typography_safety: float = 0.0
    aesthetic: float = 0.0
    artifact: float = 0.0

    def composite(self) -> float:
        vals = (
            self.composition,
            self.contrast,
            self.brand_alignment,
            self.whitespace,
            self.typography_safety,
            self.aesthetic,
            self.artifact,
        )
        return round(sum(vals) / len(vals), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition": self.composition,
            "contrast": self.contrast,
            "brand_alignment": self.brand_alignment,
            "whitespace": self.whitespace,
            "typography_safety": self.typography_safety,
            "aesthetic": self.aesthetic,
            "artifact": self.artifact,
            "composite": self.composite(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualQualityBreakdown:
        if not data:
            return VisualQualityBreakdown()
        return VisualQualityBreakdown(
            composition=float(data.get("composition") or 0.0),
            contrast=float(data.get("contrast") or 0.0),
            brand_alignment=float(data.get("brand_alignment") or 0.0),
            whitespace=float(data.get("whitespace") or 0.0),
            typography_safety=float(data.get("typography_safety") or 0.0),
            aesthetic=float(data.get("aesthetic") or 0.0),
            artifact=float(data.get("artifact") or 0.0),
        )


@dataclass(slots=True)
class LayoutRegion:
    role: str
    x: float
    y: float
    width: float
    height: float
    unit: str = "normalized"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "unit": self.unit,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> LayoutRegion:
        if not data:
            return LayoutRegion(role="", x=0.0, y=0.0, width=0.0, height=0.0)
        return LayoutRegion(
            role=str(data.get("role") or ""),
            x=float(data.get("x") or 0.0),
            y=float(data.get("y") or 0.0),
            width=float(data.get("width") or 0.0),
            height=float(data.get("height") or 0.0),
            unit=str(data.get("unit") or "normalized"),
        )


@dataclass(slots=True)
class LayoutPlan:
    """Region geometry for future typography — never renders text."""

    title: LayoutRegion | None = None
    subtitle: LayoutRegion | None = None
    cta: LayoutRegion | None = None
    logo: LayoutRegion | None = None
    footer: LayoutRegion | None = None
    icon_regions: tuple[LayoutRegion, ...] = ()
    illustration_safe: LayoutRegion | None = None
    whitespace_map: tuple[LayoutRegion, ...] = ()
    reading_direction: str = "ltr_top_to_bottom"
    alignment_guides: tuple[float, ...] = ()
    image_width: int = 0
    image_height: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title.to_dict() if self.title else None,
            "subtitle": self.subtitle.to_dict() if self.subtitle else None,
            "cta": self.cta.to_dict() if self.cta else None,
            "logo": self.logo.to_dict() if self.logo else None,
            "footer": self.footer.to_dict() if self.footer else None,
            "icon_regions": [r.to_dict() for r in self.icon_regions],
            "illustration_safe": self.illustration_safe.to_dict() if self.illustration_safe else None,
            "whitespace_map": [r.to_dict() for r in self.whitespace_map],
            "reading_direction": self.reading_direction,
            "alignment_guides": list(self.alignment_guides),
            "image_width": self.image_width,
            "image_height": self.image_height,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> LayoutPlan:
        if not data:
            return LayoutPlan()

        def _r(key: str) -> LayoutRegion | None:
            raw = data.get(key)
            return LayoutRegion.from_dict(raw) if isinstance(raw, dict) else None

        icons = tuple(
            LayoutRegion.from_dict(x) for x in (data.get("icon_regions") or []) if isinstance(x, dict)
        )
        ws = tuple(
            LayoutRegion.from_dict(x) for x in (data.get("whitespace_map") or []) if isinstance(x, dict)
        )
        return LayoutPlan(
            title=_r("title"),
            subtitle=_r("subtitle"),
            cta=_r("cta"),
            logo=_r("logo"),
            footer=_r("footer"),
            icon_regions=icons,
            illustration_safe=_r("illustration_safe"),
            whitespace_map=ws,
            reading_direction=str(data.get("reading_direction") or "ltr_top_to_bottom"),
            alignment_guides=tuple(float(x) for x in (data.get("alignment_guides") or ())),
            image_width=int(data.get("image_width") or 0),
            image_height=int(data.get("image_height") or 0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class AssetIntelligenceReport:
    dominant_colors: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    whitespace: tuple[dict[str, Any], ...] = ()
    ocr_regions: tuple[dict[str, Any], ...] = ()
    safe_crop_areas: tuple[dict[str, Any], ...] = ()
    brand_palette: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dominant_colors": list(self.dominant_colors),
            "objects": list(self.objects),
            "whitespace": list(self.whitespace),
            "ocr_regions": list(self.ocr_regions),
            "safe_crop_areas": list(self.safe_crop_areas),
            "brand_palette": list(self.brand_palette),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> AssetIntelligenceReport:
        if not data:
            return AssetIntelligenceReport()
        return AssetIntelligenceReport(
            dominant_colors=tuple(str(c) for c in (data.get("dominant_colors") or ())),
            objects=tuple(str(o) for o in (data.get("objects") or ())),
            whitespace=tuple(dict(x) for x in (data.get("whitespace") or ()) if isinstance(x, dict)),
            ocr_regions=tuple(dict(x) for x in (data.get("ocr_regions") or ()) if isinstance(x, dict)),
            safe_crop_areas=tuple(
                dict(x) for x in (data.get("safe_crop_areas") or ()) if isinstance(x, dict)
            ),
            brand_palette=tuple(str(c) for c in (data.get("brand_palette") or ())),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class VisualEmbedding:
    job_id: str
    asset_id: str = ""
    vector: tuple[float, ...] = ()
    model_id: str = "visual-hash-v1"
    dimensions: int = 0
    organization_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "asset_id": self.asset_id,
            "vector": list(self.vector),
            "model_id": self.model_id,
            "dimensions": self.dimensions,
            "organization_id": self.organization_id,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ImageValidationResult:
    passed: bool
    score: float
    resolution_ok: bool = True
    aspect_ratio_ok: bool = True
    brand_palette_ok: bool = True
    blur_ok: bool = True
    artifacts_ok: bool = True
    typography_safe_area_ok: bool = True
    file_integrity_ok: bool = True
    reason_codes: tuple[str, ...] = ()
    breakdown: VisualQualityBreakdown | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "resolution_ok": self.resolution_ok,
            "aspect_ratio_ok": self.aspect_ratio_ok,
            "brand_palette_ok": self.brand_palette_ok,
            "blur_ok": self.blur_ok,
            "artifacts_ok": self.artifacts_ok,
            "typography_safe_area_ok": self.typography_safe_area_ok,
            "file_integrity_ok": self.file_integrity_ok,
            "reason_codes": list(self.reason_codes),
            "breakdown": self.breakdown.to_dict() if self.breakdown else None,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class OptimizedImageBundle:
    original_bytes: bytes
    optimized_bytes: bytes
    thumbnail_bytes: bytes
    width: int
    height: int
    thumb_width: int
    thumb_height: int
    formats: dict[str, bytes] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImageAssetRecord:
    asset_id: str
    job_id: str
    role: str
    object_key: str
    width: int
    height: int
    sha256: str = ""
    mime_type: str = "image/png"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "job_id": self.job_id,
            "role": self.role,
            "object_key": self.object_key,
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
            "mime_type": self.mime_type,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class WorkflowDescriptor:
    workflow_id: str
    version: str
    provider: str
    model: str
    path: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "version": self.version,
            "provider": self.provider,
            "model": self.model,
            "path": self.path,
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ImagePipelineRequest:
    organization_id: str
    draft_id: str
    draft: dict[str, Any]
    content_plan: dict[str, Any] = field(default_factory=dict)
    brand: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    preferred_workflow_id: str | None = None
    replay_of_job_id: str | None = None
    variant_index: int = 0
    image_count: int = 1
    seed_override: int | None = None
    # Real brand logo bytes, in-memory only — see ImageGenerationRequest.logo_bytes.
    logo_bytes: bytes | None = None


@dataclass(slots=True)
class ImagePipelineResult:
    job_id: str
    status: str
    brief: EnrichedVisualBrief
    scene: ScenePlan
    composition: CompositionPlan
    policy: VisualPolicyResult
    prompt_request: ImagePromptRequest
    validation: ImageValidationResult
    assets: tuple[ImageAssetRecord, ...] = ()
    layout: LayoutPlan | None = None
    asset_intelligence: AssetIntelligenceReport | None = None
    embedding: VisualEmbedding | None = None
    quality: VisualQualityBreakdown | None = None
    provider: str = ""
    model: str = ""
    quality_score: float = 0.0
    latency_ms: int = 0
    cost_estimate: float | None = None
    queue_time_ms: int = 0
    retry_count: int = 0
    prompt_hash: str = ""
    workflow_id: str = ""
    workflow_version: str = ""
    seed: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "brief": self.brief.to_dict(),
            "scene": self.scene.to_dict(),
            "composition": self.composition.to_dict(),
            "policy": self.policy.to_dict(),
            "prompt_request": self.prompt_request.to_dict(),
            "validation": self.validation.to_dict(),
            "assets": [a.to_dict() for a in self.assets],
            "layout": self.layout.to_dict() if self.layout else None,
            "asset_intelligence": (
                self.asset_intelligence.to_dict() if self.asset_intelligence else None
            ),
            "embedding": self.embedding.to_dict() if self.embedding else None,
            "quality": self.quality.to_dict() if self.quality else None,
            "provider": self.provider,
            "model": self.model,
            "quality_score": self.quality_score,
            "latency_ms": self.latency_ms,
            "cost_estimate": self.cost_estimate,
            "queue_time_ms": self.queue_time_ms,
            "retry_count": self.retry_count,
            "prompt_hash": self.prompt_hash,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "seed": self.seed,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ImageReplayRecord:
    replay_id: str
    job_id: str
    prompt_request: dict[str, Any]
    scene: dict[str, Any]
    composition: dict[str, Any]
    provider: str
    workflow_id: str
    workflow_version: str
    visual_brief: dict[str, Any] = field(default_factory=dict)
    layout: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    asset_refs: tuple[dict[str, Any], ...] = ()
    quality_breakdown: dict[str, Any] = field(default_factory=dict)
    result_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "job_id": self.job_id,
            "prompt_request": dict(self.prompt_request),
            "scene": dict(self.scene),
            "composition": dict(self.composition),
            "provider": self.provider,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "visual_brief": dict(self.visual_brief),
            "layout": dict(self.layout),
            "seed": self.seed,
            "asset_refs": list(self.asset_refs),
            "quality_breakdown": dict(self.quality_breakdown),
            "result_metadata": dict(self.result_metadata),
        }


@dataclass(slots=True)
class ImageDiff:
    left_job_id: str
    right_job_id: str
    field_changes: dict[str, Any] = field(default_factory=dict)
    prompt_changed: bool = False
    workflow_changed: bool = False
    provider_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_job_id": self.left_job_id,
            "right_job_id": self.right_job_id,
            "field_changes": dict(self.field_changes),
            "prompt_changed": self.prompt_changed,
            "workflow_changed": self.workflow_changed,
            "provider_changed": self.provider_changed,
        }


def new_job_id() -> str:
    return str(uuid.uuid4())
