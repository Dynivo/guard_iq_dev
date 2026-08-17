"""Visual Design Specification — structured creative plan before illustration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ARCHETYPE_IDS = (
    "statistic_threat_alert",
    "statistic_infographic",
    "data_infographic",
    "threat_alert",
    "threat_risk_map",
    "central_hub",
    "process_flow",
    "timeline",
    "risk_map",
    "explainer_infographic",
    "comparison",
    "quote_insight",
    "news_alert",
    "minimal_editorial",
)


@dataclass(slots=True)
class DesignBrandColors:
    primary: str = "#0A1F2B"
    secondary: str = "#FFFFFF"
    background: str = "#0A1F2B"
    text: str = "#FFFFFF"
    accent: str = "#4FC3F7"

    def to_dict(self) -> dict[str, str]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "background": self.background,
            "text": self.text,
            "accent": self.accent,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DesignBrandColors:
        d = data or {}
        return DesignBrandColors(
            primary=str(d.get("primary") or "#0A1F2B"),
            secondary=str(d.get("secondary") or "#FFFFFF"),
            background=str(d.get("background") or d.get("primary") or "#0A1F2B"),
            text=str(d.get("text") or "#FFFFFF"),
            accent=str(d.get("accent") or "#4FC3F7"),
        )


@dataclass(slots=True)
class DesignLogoSpec:
    enabled: bool = True
    position: str = "bottom_right"
    size: str = "m"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "position": self.position,
            "size": self.size,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DesignLogoSpec:
        d = data or {}
        return DesignLogoSpec(
            enabled=bool(d.get("enabled", d.get("include_logo", True))),
            position=str(d.get("position") or "bottom_right"),
            size=str(d.get("size") or "m").lower(),
        )


@dataclass(slots=True)
class DesignLayoutSpec:
    type: str = "threat_alert"
    columns: int = 1
    density: str = "medium"
    width: int = 1080
    height: int = 1080

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "columns": self.columns,
            "density": self.density,
            "width": self.width,
            "height": self.height,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DesignLayoutSpec:
        d = data or {}
        return DesignLayoutSpec(
            type=str(d.get("type") or "threat_alert"),
            columns=int(d.get("columns") or 1),
            density=str(d.get("density") or "medium"),
            width=int(d.get("width") or 1080),
            height=int(d.get("height") or 1080),
        )


@dataclass(slots=True)
class VisualStatistic:
    """A verified numeric/metric callout for infographic layouts."""

    value: str = ""
    label: str = ""
    role: str = "supporting"  # hero | supporting | context

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "label": self.label, "role": self.role}

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualStatistic:
        d = data or {}
        role = str(d.get("role") or "supporting").lower()
        if role not in {"hero", "supporting", "context"}:
            role = "supporting"
        return VisualStatistic(
            value=str(d.get("value") or ""),
            label=str(d.get("label") or ""),
            role=role,
        )


@dataclass(slots=True)
class VisualRelationship:
    """Directed relationship between visual nodes (hub, flow, risk map)."""

    from_node: str = ""
    to_node: str = ""
    label: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "label": self.label,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualRelationship:
        d = data or {}
        return VisualRelationship(
            from_node=str(d.get("from_node") or d.get("from") or ""),
            to_node=str(d.get("to_node") or d.get("to") or ""),
            label=str(d.get("label") or ""),
        )


@dataclass(slots=True)
class VisualStory:
    """Narrative framing for art direction (not rendered as raw copy)."""

    narrative: str = ""
    metaphor: str = ""
    viewer_takeaway: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "narrative": self.narrative,
            "metaphor": self.metaphor,
            "viewer_takeaway": self.viewer_takeaway,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualStory:
        d = data or {}
        return VisualStory(
            narrative=str(d.get("narrative") or ""),
            metaphor=str(d.get("metaphor") or ""),
            viewer_takeaway=str(d.get("viewer_takeaway") or ""),
        )


@dataclass(slots=True)
class VisualHierarchy:
    """Layout hierarchy / density / complexity hints for Gemini art direction."""

    primary_focus: str = "headline"
    secondary_focus: str = "stat"
    density: str = "medium"  # low | medium | high
    complexity: str = "moderate"  # simple | moderate | rich
    coverage_hint: str = "filled_infographic"  # sparse | balanced | filled_infographic

    def to_dict(self) -> dict[str, str]:
        return {
            "primary_focus": self.primary_focus,
            "secondary_focus": self.secondary_focus,
            "density": self.density,
            "complexity": self.complexity,
            "coverage_hint": self.coverage_hint,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualHierarchy:
        d = data or {}
        return VisualHierarchy(
            primary_focus=str(d.get("primary_focus") or "headline"),
            secondary_focus=str(d.get("secondary_focus") or "stat"),
            density=str(d.get("density") or "medium"),
            complexity=str(d.get("complexity") or "moderate"),
            coverage_hint=str(d.get("coverage_hint") or "filled_infographic"),
        )


@dataclass(slots=True)
class VisualDesignSpec:
    """Application-owned creative plan for hybrid and Gemini infographic modes."""

    format: str = "linkedin_square"
    design_archetype: str = "statistic_threat_alert"
    headline: str = ""
    subheadline: str = ""
    primary_stat: str = ""
    supporting_stats: tuple[str, ...] = ()
    visual_concept: str = ""
    visual_elements: tuple[str, ...] = ()
    content_blocks: tuple[str, ...] = ()
    cta: str = ""
    cta_body: str = ""
    source: str = ""
    category_label: str = ""
    brand_name: str = ""
    tagline: str = ""
    logo: DesignLogoSpec = field(default_factory=DesignLogoSpec)
    brand: DesignBrandColors = field(default_factory=DesignBrandColors)
    layout: DesignLayoutSpec = field(default_factory=DesignLayoutSpec)
    typography_template: str = "statistics"
    brand_variant: str = "dark"
    visual_motifs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    # Additive Gemini / visual-story fields (optional; backward compatible)
    statistics: tuple[VisualStatistic, ...] = ()
    relationships: tuple[VisualRelationship, ...] = ()
    story: VisualStory = field(default_factory=VisualStory)
    hierarchy: VisualHierarchy = field(default_factory=VisualHierarchy)
    factual_constraints: tuple[str, ...] = ()
    image_generation_instruction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "design_archetype": self.design_archetype,
            "headline": self.headline,
            "subheadline": self.subheadline,
            "primary_stat": self.primary_stat,
            "supporting_stats": list(self.supporting_stats),
            "visual_concept": self.visual_concept,
            "visual_elements": list(self.visual_elements),
            "content_blocks": list(self.content_blocks),
            "cta": self.cta,
            "cta_body": self.cta_body,
            "source": self.source,
            "category_label": self.category_label,
            "brand_name": self.brand_name,
            "tagline": self.tagline,
            "logo": self.logo.to_dict(),
            "brand": self.brand.to_dict(),
            "layout": self.layout.to_dict(),
            "typography_template": self.typography_template,
            "brand_variant": self.brand_variant,
            "visual_motifs": list(self.visual_motifs),
            "metadata": dict(self.metadata),
            "statistics": [s.to_dict() for s in self.statistics],
            "relationships": [r.to_dict() for r in self.relationships],
            "story": self.story.to_dict(),
            "hierarchy": self.hierarchy.to_dict(),
            "factual_constraints": list(self.factual_constraints),
            "image_generation_instruction": self.image_generation_instruction,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> VisualDesignSpec:
        if not data:
            return VisualDesignSpec()
        stats_raw = data.get("statistics") or ()
        rel_raw = data.get("relationships") or ()
        return VisualDesignSpec(
            format=str(data.get("format") or "linkedin_square"),
            design_archetype=str(data.get("design_archetype") or "statistic_threat_alert"),
            headline=str(data.get("headline") or ""),
            subheadline=str(data.get("subheadline") or ""),
            primary_stat=str(data.get("primary_stat") or ""),
            supporting_stats=tuple(
                str(x) for x in (data.get("supporting_stats") or ()) if str(x).strip()
            ),
            visual_concept=str(data.get("visual_concept") or ""),
            visual_elements=tuple(
                str(x) for x in (data.get("visual_elements") or ()) if str(x).strip()
            ),
            content_blocks=tuple(
                str(x) for x in (data.get("content_blocks") or ()) if str(x).strip()
            ),
            cta=str(data.get("cta") or ""),
            cta_body=str(data.get("cta_body") or ""),
            source=str(data.get("source") or ""),
            category_label=str(data.get("category_label") or ""),
            brand_name=str(data.get("brand_name") or ""),
            tagline=str(data.get("tagline") or ""),
            logo=DesignLogoSpec.from_dict(
                data.get("logo") if isinstance(data.get("logo"), dict) else None
            ),
            brand=DesignBrandColors.from_dict(
                data.get("brand") if isinstance(data.get("brand"), dict) else None
            ),
            layout=DesignLayoutSpec.from_dict(
                data.get("layout") if isinstance(data.get("layout"), dict) else None
            ),
            typography_template=str(data.get("typography_template") or "statistics"),
            brand_variant=str(data.get("brand_variant") or "dark"),
            visual_motifs=tuple(
                str(x) for x in (data.get("visual_motifs") or ()) if str(x).strip()
            ),
            metadata=dict(data.get("metadata") or {}),
            statistics=tuple(
                VisualStatistic.from_dict(x) for x in stats_raw if isinstance(x, dict)
            ),
            relationships=tuple(
                VisualRelationship.from_dict(x) for x in rel_raw if isinstance(x, dict)
            ),
            story=VisualStory.from_dict(
                data.get("story") if isinstance(data.get("story"), dict) else None
            ),
            hierarchy=VisualHierarchy.from_dict(
                data.get("hierarchy") if isinstance(data.get("hierarchy"), dict) else None
            ),
            factual_constraints=tuple(
                str(x) for x in (data.get("factual_constraints") or ()) if str(x).strip()
            ),
            image_generation_instruction=str(data.get("image_generation_instruction") or ""),
        )
