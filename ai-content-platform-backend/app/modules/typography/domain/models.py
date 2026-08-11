"""Brand & Typography Engine domain models (M11)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LayoutEnrichment:
    """Enriched layout — grid/margins/safe zones; never renders text."""

    layout_plan: dict[str, Any]
    grid_columns: int = 12
    grid_gutter: float = 0.02
    margin_top: float = 0.04
    margin_right: float = 0.06
    margin_bottom: float = 0.04
    margin_left: float = 0.06
    safe_overlay_zones: tuple[dict[str, Any], ...] = ()
    visual_hierarchy: tuple[str, ...] = ("title", "subtitle", "cta", "footer", "logo")
    width: int = 1080
    height: int = 1350
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout_plan": dict(self.layout_plan),
            "grid_columns": self.grid_columns,
            "grid_gutter": self.grid_gutter,
            "margin_top": self.margin_top,
            "margin_right": self.margin_right,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "safe_overlay_zones": list(self.safe_overlay_zones),
            "visual_hierarchy": list(self.visual_hierarchy),
            "width": self.width,
            "height": self.height,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> LayoutEnrichment:
        if not data:
            return LayoutEnrichment(layout_plan={})
        return LayoutEnrichment(
            layout_plan=dict(data.get("layout_plan") or {}),
            grid_columns=int(data.get("grid_columns") or 12),
            grid_gutter=float(data.get("grid_gutter") or 0.02),
            margin_top=float(data.get("margin_top") or 0.04),
            margin_right=float(data.get("margin_right") or 0.06),
            margin_bottom=float(data.get("margin_bottom") or 0.04),
            margin_left=float(data.get("margin_left") or 0.06),
            safe_overlay_zones=tuple(
                dict(x) for x in (data.get("safe_overlay_zones") or ()) if isinstance(x, dict)
            ),
            visual_hierarchy=tuple(str(x) for x in (data.get("visual_hierarchy") or ())),
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class TextStyleSpec:
    role: str
    font_family: str = "Inter"
    font_size: float = 48.0
    font_weight: int = 700
    line_height: float = 1.2
    letter_spacing: float = 0.0
    alignment: str = "left"
    color_token: str = "text_primary"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "line_height": self.line_height,
            "letter_spacing": self.letter_spacing,
            "alignment": self.alignment,
            "color_token": self.color_token,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> TextStyleSpec:
        if not data:
            return TextStyleSpec(role="")
        return TextStyleSpec(
            role=str(data.get("role") or ""),
            font_family=str(data.get("font_family") or "Inter"),
            font_size=float(data.get("font_size") or 48.0),
            font_weight=int(data.get("font_weight") or 700),
            line_height=float(data.get("line_height") or 1.2),
            letter_spacing=float(data.get("letter_spacing") or 0.0),
            alignment=str(data.get("alignment") or "left"),
            color_token=str(data.get("color_token") or "text_primary"),
        )


@dataclass(slots=True)
class TypographyPlan:
    styles: tuple[TextStyleSpec, ...] = ()
    spacing_scale: float = 1.0
    hierarchy: tuple[str, ...] = ()
    template_id: str = "default"
    width: int = 1080
    height: int = 1350
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "styles": [s.to_dict() for s in self.styles],
            "spacing_scale": self.spacing_scale,
            "hierarchy": list(self.hierarchy),
            "template_id": self.template_id,
            "width": self.width,
            "height": self.height,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> TypographyPlan:
        if not data:
            return TypographyPlan()
        styles = tuple(
            TextStyleSpec.from_dict(x) for x in (data.get("styles") or []) if isinstance(x, dict)
        )
        return TypographyPlan(
            styles=styles,
            spacing_scale=float(data.get("spacing_scale") or 1.0),
            hierarchy=tuple(str(x) for x in (data.get("hierarchy") or ())),
            template_id=str(data.get("template_id") or "default"),
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class DesignTokens:
    """Expanded design token groups for themes and future multi-brand."""

    typography: dict[str, Any] = field(default_factory=dict)
    spacing: dict[str, Any] = field(default_factory=dict)
    radius: dict[str, Any] = field(default_factory=dict)
    elevation: dict[str, Any] = field(default_factory=dict)
    shadows: dict[str, Any] = field(default_factory=dict)
    borders: dict[str, Any] = field(default_factory=dict)
    opacity: dict[str, Any] = field(default_factory=dict)
    animation: dict[str, Any] = field(default_factory=dict)
    colors: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "typography": dict(self.typography),
            "spacing": dict(self.spacing),
            "radius": dict(self.radius),
            "elevation": dict(self.elevation),
            "shadows": dict(self.shadows),
            "borders": dict(self.borders),
            "opacity": dict(self.opacity),
            "animation": dict(self.animation),
            "colors": dict(self.colors),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DesignTokens:
        if not data:
            return DesignTokens()
        return DesignTokens(
            typography=dict(data.get("typography") or {}),
            spacing=dict(data.get("spacing") or {}),
            radius=dict(data.get("radius") or {}),
            elevation=dict(data.get("elevation") or {}),
            shadows=dict(data.get("shadows") or {}),
            borders=dict(data.get("borders") or {}),
            opacity=dict(data.get("opacity") or {}),
            animation=dict(data.get("animation") or {}),
            colors=dict(data.get("colors") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class TypographyIntelligence:
    readability: float = 0.0
    scanability: float = 0.0
    density: float = 0.0
    hierarchy: float = 0.0
    whitespace: float = 0.0

    def composite(self) -> float:
        vals = (
            self.readability,
            self.scanability,
            self.density,
            self.hierarchy,
            self.whitespace,
        )
        return round(sum(vals) / len(vals), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "readability": self.readability,
            "scanability": self.scanability,
            "density": self.density,
            "hierarchy": self.hierarchy,
            "whitespace": self.whitespace,
            "composite": self.composite(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> TypographyIntelligence:
        if not data:
            return TypographyIntelligence()
        return TypographyIntelligence(
            readability=float(data.get("readability") or 0.0),
            scanability=float(data.get("scanability") or 0.0),
            density=float(data.get("density") or 0.0),
            hierarchy=float(data.get("hierarchy") or 0.0),
            whitespace=float(data.get("whitespace") or 0.0),
        )


@dataclass(slots=True)
class SlideCompositionMetadata:
    """Hints for M12 carousel — never renders slides."""

    preferred_slide_type: str = "single"
    preferred_layout: str = "default"
    visual_weight: float = 0.5
    reading_flow: str = "ltr_top_to_bottom"
    emphasis_score: float = 0.5
    transition_hint: str = "none"
    continuation_hint: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_slide_type": self.preferred_slide_type,
            "preferred_layout": self.preferred_layout,
            "visual_weight": self.visual_weight,
            "reading_flow": self.reading_flow,
            "emphasis_score": self.emphasis_score,
            "transition_hint": self.transition_hint,
            "continuation_hint": self.continuation_hint,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> SlideCompositionMetadata:
        if not data:
            return SlideCompositionMetadata()
        return SlideCompositionMetadata(
            preferred_slide_type=str(data.get("preferred_slide_type") or "single"),
            preferred_layout=str(data.get("preferred_layout") or "default"),
            visual_weight=float(data.get("visual_weight") or 0.5),
            reading_flow=str(data.get("reading_flow") or "ltr_top_to_bottom"),
            emphasis_score=float(data.get("emphasis_score") or 0.5),
            transition_hint=str(data.get("transition_hint") or "none"),
            continuation_hint=str(data.get("continuation_hint") or "none"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class BrandApplication:
    brand_id: str = ""
    brand_name: str = ""
    primary_color: str = "#0A1F2B"
    secondary_color: str = "#FFFFFF"
    accent_color: str = "#1A5CB0"
    text_color: str = "#FFFFFF"
    font_heading: str = "Inter"
    font_body: str = "Inter"
    logo_object_key: str | None = None
    footer_text: str = ""
    services_line: str = ""
    variant: str = "dark"
    min_contrast_ratio: float = 4.5
    tokens: dict[str, Any] = field(default_factory=dict)
    design_tokens: DesignTokens | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "text_color": self.text_color,
            "font_heading": self.font_heading,
            "font_body": self.font_body,
            "logo_object_key": self.logo_object_key,
            "footer_text": self.footer_text,
            "services_line": self.services_line,
            "variant": self.variant,
            "min_contrast_ratio": self.min_contrast_ratio,
            "tokens": dict(self.tokens),
            "design_tokens": self.design_tokens.to_dict() if self.design_tokens else None,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> BrandApplication:
        if not data:
            return BrandApplication()
        return BrandApplication(
            brand_id=str(data.get("brand_id") or ""),
            brand_name=str(data.get("brand_name") or ""),
            primary_color=str(data.get("primary_color") or "#0A1F2B"),
            secondary_color=str(data.get("secondary_color") or "#FFFFFF"),
            accent_color=str(data.get("accent_color") or "#1A5CB0"),
            text_color=str(data.get("text_color") or "#FFFFFF"),
            font_heading=str(data.get("font_heading") or "Inter"),
            font_body=str(data.get("font_body") or "Inter"),
            logo_object_key=data.get("logo_object_key"),
            footer_text=str(data.get("footer_text") or ""),
            services_line=str(data.get("services_line") or ""),
            variant=str(data.get("variant") or "dark"),
            min_contrast_ratio=float(data.get("min_contrast_ratio") or 4.5),
            tokens=dict(data.get("tokens") or {}),
            design_tokens=DesignTokens.from_dict(data.get("design_tokens")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class SvgLayer:
    layer_id: str
    kind: str  # text | image | shape | logo | icon | group
    role: str
    content: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    parent: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    z_index: int = 0
    anchor: str = "top_left"
    visibility: str = "visible"
    animation: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.layer_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.layer_id,
            "layer_id": self.layer_id,
            "kind": self.kind,
            "role": self.role,
            "content": self.content,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "parent": self.parent,
            "constraints": dict(self.constraints),
            "z_index": self.z_index,
            "anchor": self.anchor,
            "visibility": self.visibility,
            "animation": dict(self.animation),
            "style": dict(self.style),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> SvgLayer:
        if not data:
            return SvgLayer(layer_id="", kind="text", role="")
        lid = str(data.get("layer_id") or data.get("id") or "")
        return SvgLayer(
            layer_id=lid,
            kind=str(data.get("kind") or "text"),
            role=str(data.get("role") or ""),
            content=str(data.get("content") or ""),
            x=float(data.get("x") or 0.0),
            y=float(data.get("y") or 0.0),
            width=float(data.get("width") or 0.0),
            height=float(data.get("height") or 0.0),
            parent=data.get("parent"),
            constraints=dict(data.get("constraints") or {}),
            z_index=int(data.get("z_index") or 0),
            anchor=str(data.get("anchor") or "top_left"),
            visibility=str(data.get("visibility") or "visible"),
            animation=dict(data.get("animation") or {}),
            style=dict(data.get("style") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class OverlayValidationResult:
    passed: bool = True
    overflow_ok: bool = True
    margins_ok: bool = True
    contrast_ok: bool = True
    font_size_ok: bool = True
    collisions_ok: bool = True
    logo_ok: bool = True
    accessibility_score: float = 1.0
    contrast_score: float = 1.0
    typography_score: float = 1.0
    overflow_rate: float = 0.0
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "overflow_ok": self.overflow_ok,
            "margins_ok": self.margins_ok,
            "contrast_ok": self.contrast_ok,
            "font_size_ok": self.font_size_ok,
            "collisions_ok": self.collisions_ok,
            "logo_ok": self.logo_ok,
            "accessibility_score": self.accessibility_score,
            "contrast_score": self.contrast_score,
            "typography_score": self.typography_score,
            "overflow_rate": self.overflow_rate,
            "reason_codes": list(self.reason_codes),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class BrandValidationResult:
    passed: bool = True
    colors_ok: bool = True
    fonts_ok: bool = True
    spacing_ok: bool = True
    alignment_ok: bool = True
    compliance_ok: bool = True
    brand_score: float = 1.0
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "colors_ok": self.colors_ok,
            "fonts_ok": self.fonts_ok,
            "spacing_ok": self.spacing_ok,
            "alignment_ok": self.alignment_ok,
            "compliance_ok": self.compliance_ok,
            "brand_score": self.brand_score,
            "reason_codes": list(self.reason_codes),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class TypographyAsset:
    asset_id: str
    svg: str
    layers: tuple[SvgLayer, ...]
    width: int
    height: int
    layout: LayoutEnrichment | None = None
    typography_plan: TypographyPlan | None = None
    brand: BrandApplication | None = None
    overlay_validation: OverlayValidationResult | None = None
    brand_validation: BrandValidationResult | None = None
    slide_composition: SlideCompositionMetadata | None = None
    intelligence: TypographyIntelligence | None = None
    illustration_ref: str = ""
    version: int = 1
    parent_asset_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "svg": self.svg,
            "layers": [layer.to_dict() for layer in self.layers],
            "width": self.width,
            "height": self.height,
            "layout": self.layout.to_dict() if self.layout else None,
            "typography_plan": self.typography_plan.to_dict() if self.typography_plan else None,
            "brand": self.brand.to_dict() if self.brand else None,
            "overlay_validation": (
                self.overlay_validation.to_dict() if self.overlay_validation else None
            ),
            "brand_validation": (
                self.brand_validation.to_dict() if self.brand_validation else None
            ),
            "slide_composition": (
                self.slide_composition.to_dict() if self.slide_composition else None
            ),
            "intelligence": self.intelligence.to_dict() if self.intelligence else None,
            "illustration_ref": self.illustration_ref,
            "version": self.version,
            "parent_asset_id": self.parent_asset_id,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class TypographyCopy:
    headline: str = ""
    subtitle: str = ""
    cta: str = ""
    footer: str = ""
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "subtitle": self.subtitle,
            "cta": self.cta,
            "footer": self.footer,
            "labels": list(self.labels),
        }


@dataclass(slots=True)
class LogoPlacementOptions:
    """Typography-only logo compositing options (ADR 0063 / 0070). Never diffusion."""

    include_logo: bool = False  # optional — user opts in; brand logo never forced
    position: str = "bottom_right"  # top_left|top_right|bottom_left|bottom_right|center|custom
    custom_x: float | None = None  # 0–1 when position=custom
    custom_y: float | None = None
    size: str = "m"  # s|m|l
    opacity: float = 1.0
    margin: float = 0.04  # fraction of min(width,height)
    safe_area: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "include_logo": self.include_logo,
            "position": self.position,
            "custom_x": self.custom_x,
            "custom_y": self.custom_y,
            "size": self.size,
            "opacity": self.opacity,
            "margin": self.margin,
            "safe_area": self.safe_area,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> LogoPlacementOptions:
        if not data:
            return LogoPlacementOptions()
        return LogoPlacementOptions(
            include_logo=bool(data.get("include_logo", False)),
            position=str(data.get("position") or "bottom_right"),
            custom_x=float(data["custom_x"]) if data.get("custom_x") is not None else None,
            custom_y=float(data["custom_y"]) if data.get("custom_y") is not None else None,
            size=str(data.get("size") or "m").lower(),
            opacity=float(data.get("opacity") if data.get("opacity") is not None else 1.0),
            margin=float(data.get("margin") if data.get("margin") is not None else 0.04),
            safe_area=bool(data.get("safe_area", True)),
        )


@dataclass(slots=True)
class TypographyPipelineRequest:
    organization_id: str
    draft_id: str
    image_job_id: str = ""
    layout_plan: dict[str, Any] = field(default_factory=dict)
    brand_kit: dict[str, Any] = field(default_factory=dict)
    copy: TypographyCopy = field(default_factory=TypographyCopy)
    illustration_ref: str = ""
    target_width: int = 1080
    target_height: int = 1350
    brand_variant: str = "dark"
    template_id: str = "default"
    correlation_id: str = ""
    replay_of_asset_id: str | None = None
    logo_options: LogoPlacementOptions = field(default_factory=LogoPlacementOptions)
    logo_data_uri: str | None = None  # data:image/...;base64,... when include_logo + key resolved


@dataclass(slots=True)
class TypographyPipelineResult:
    asset: TypographyAsset
    status: str
    render_time_ms: int = 0
    validation_time_ms: int = 0
    slide_composition: SlideCompositionMetadata | None = None
    intelligence: TypographyIntelligence | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset.to_dict(),
            "status": self.status,
            "render_time_ms": self.render_time_ms,
            "validation_time_ms": self.validation_time_ms,
            "slide_composition": (
                self.slide_composition.to_dict() if self.slide_composition else None
            ),
            "intelligence": self.intelligence.to_dict() if self.intelligence else None,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class TypographyReplayRecord:
    replay_id: str
    asset_id: str
    request_snapshot: dict[str, Any]
    result_snapshot: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "asset_id": self.asset_id,
            "request_snapshot": dict(self.request_snapshot),
            "result_snapshot": dict(self.result_snapshot),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class OverlayDiff:
    left_asset_id: str
    right_asset_id: str
    layer_changes: dict[str, Any] = field(default_factory=dict)
    brand_changed: bool = False
    plan_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_asset_id": self.left_asset_id,
            "right_asset_id": self.right_asset_id,
            "layer_changes": dict(self.layer_changes),
            "brand_changed": self.brand_changed,
            "plan_changed": self.plan_changed,
        }


def new_asset_id() -> str:
    return str(uuid.uuid4())
