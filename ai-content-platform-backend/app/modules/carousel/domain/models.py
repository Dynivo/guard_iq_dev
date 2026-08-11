"""Carousel Composition & Rendering Engine domain models (M12)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass(slots=True)
class PlannedSlide:
    index: int
    purpose: str  # hook | educational | problem | solution | cta | summary | context | ...
    title: str = ""
    body: str = ""
    transition_hint: str = "none"
    continuation_hint: str = "none"
    preferred_layout: str = "default"
    typography_asset_id: str | None = None
    image_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "purpose": self.purpose,
            "title": self.title,
            "body": self.body,
            "transition_hint": self.transition_hint,
            "continuation_hint": self.continuation_hint,
            "preferred_layout": self.preferred_layout,
            "typography_asset_id": self.typography_asset_id,
            "image_ref": self.image_ref,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> PlannedSlide:
        if not data:
            return PlannedSlide(index=0, purpose="educational")
        return PlannedSlide(
            index=int(data.get("index") or 0),
            purpose=str(data.get("purpose") or "educational"),
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            transition_hint=str(data.get("transition_hint") or "none"),
            continuation_hint=str(data.get("continuation_hint") or "none"),
            preferred_layout=str(data.get("preferred_layout") or "default"),
            typography_asset_id=data.get("typography_asset_id"),
            image_ref=str(data.get("image_ref") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class CarouselPlan:
    slides: tuple[PlannedSlide, ...] = ()
    slide_count: int = 0
    sequence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slides": [s.to_dict() for s in self.slides],
            "slide_count": self.slide_count or len(self.slides),
            "sequence": list(self.sequence),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> CarouselPlan:
        if not data:
            return CarouselPlan()
        slides = tuple(
            PlannedSlide.from_dict(x) for x in (data.get("slides") or []) if isinstance(x, dict)
        )
        return CarouselPlan(
            slides=slides,
            slide_count=int(data.get("slide_count") or len(slides)),
            sequence=tuple(str(x) for x in (data.get("sequence") or ())),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ComposedLayerRef:
    """Reference to an existing typography/image layer — never mutates source."""

    layer_id: str
    role: str
    kind: str
    source: str  # typography | image | logo | icon
    z_index: int = 0
    anchor: str = "top_left"
    visibility: str = "visible"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "role": self.role,
            "kind": self.kind,
            "source": self.source,
            "z_index": self.z_index,
            "anchor": self.anchor,
            "visibility": self.visibility,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class SlideComposition:
    """Arranged layers for one slide — no rendering."""

    slide_index: int
    purpose: str
    layers: tuple[ComposedLayerRef, ...] = ()
    grid_columns: int = 12
    safe_areas: tuple[dict[str, Any], ...] = ()
    visual_balance: float = 0.5
    whitespace_score: float = 0.5
    alignment: str = "left"
    svg_fragment: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "purpose": self.purpose,
            "layers": [L.to_dict() for L in self.layers],
            "grid_columns": self.grid_columns,
            "safe_areas": list(self.safe_areas),
            "visual_balance": self.visual_balance,
            "whitespace_score": self.whitespace_score,
            "alignment": self.alignment,
            "svg_fragment": self.svg_fragment,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> SlideComposition:
        if not data:
            return SlideComposition(slide_index=0, purpose="educational")
        layers = tuple(
            ComposedLayerRef(
                layer_id=str(x.get("layer_id") or ""),
                role=str(x.get("role") or ""),
                kind=str(x.get("kind") or "text"),
                source=str(x.get("source") or "typography"),
                z_index=int(x.get("z_index") or 0),
                anchor=str(x.get("anchor") or "top_left"),
                visibility=str(x.get("visibility") or "visible"),
                metadata=dict(x.get("metadata") or {}),
            )
            for x in (data.get("layers") or [])
            if isinstance(x, dict)
        )
        return SlideComposition(
            slide_index=int(data.get("slide_index") or 0),
            purpose=str(data.get("purpose") or "educational"),
            layers=layers,
            grid_columns=int(data.get("grid_columns") or 12),
            safe_areas=tuple(dict(x) for x in (data.get("safe_areas") or ()) if isinstance(x, dict)),
            visual_balance=float(data.get("visual_balance") or 0.5),
            whitespace_score=float(data.get("whitespace_score") or 0.5),
            alignment=str(data.get("alignment") or "left"),
            svg_fragment=str(data.get("svg_fragment") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class DeckSlide:
    slide_id: str
    index: int
    purpose: str
    title: str = ""
    body: str = ""
    composition: SlideComposition | None = None
    prev_slide_id: str | None = None
    next_slide_id: str | None = None
    transition_hint: str = "none"
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "index": self.index,
            "purpose": self.purpose,
            "title": self.title,
            "body": self.body,
            "composition": self.composition.to_dict() if self.composition else None,
            "prev_slide_id": self.prev_slide_id,
            "next_slide_id": self.next_slide_id,
            "transition_hint": self.transition_hint,
            "version": self.version,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DeckSlide:
        if not data:
            return DeckSlide(slide_id=new_id(), index=0, purpose="educational")
        return DeckSlide(
            slide_id=str(data.get("slide_id") or new_id()),
            index=int(data.get("index") or 0),
            purpose=str(data.get("purpose") or "educational"),
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            composition=SlideComposition.from_dict(data.get("composition")),
            prev_slide_id=data.get("prev_slide_id"),
            next_slide_id=data.get("next_slide_id"),
            transition_hint=str(data.get("transition_hint") or "none"),
            version=int(data.get("version") or 1),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class Deck:
    deck_id: str
    title: str = ""
    slides: tuple[DeckSlide, ...] = ()
    version: int = 1
    parent_deck_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deck_id": self.deck_id,
            "title": self.title,
            "slides": [s.to_dict() for s in self.slides],
            "version": self.version,
            "parent_deck_id": self.parent_deck_id,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> Deck:
        if not data:
            return Deck(deck_id=new_id())
        return Deck(
            deck_id=str(data.get("deck_id") or new_id()),
            title=str(data.get("title") or ""),
            slides=tuple(
                DeckSlide.from_dict(x) for x in (data.get("slides") or []) if isinstance(x, dict)
            ),
            version=int(data.get("version") or 1),
            parent_deck_id=data.get("parent_deck_id"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class LayoutConstraints:
    """Margins, padding, safe areas, bleed, grid, alignment — on every deck definition."""

    margins: dict[str, float] = field(
        default_factory=lambda: {"top": 0.04, "right": 0.06, "bottom": 0.04, "left": 0.06}
    )
    padding: dict[str, float] = field(
        default_factory=lambda: {"top": 0.02, "right": 0.02, "bottom": 0.02, "left": 0.02}
    )
    safe_areas: tuple[dict[str, Any], ...] = ()
    bleed: float = 0.0
    grid_columns: int = 12
    grid_gutter: float = 0.02
    alignment_rules: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "margins": dict(self.margins),
            "padding": dict(self.padding),
            "safe_areas": list(self.safe_areas),
            "bleed": self.bleed,
            "grid_columns": self.grid_columns,
            "grid_gutter": self.grid_gutter,
            "alignment_rules": dict(self.alignment_rules),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> LayoutConstraints:
        if not data:
            return LayoutConstraints()
        return LayoutConstraints(
            margins=dict(data.get("margins") or {"top": 0.04, "right": 0.06, "bottom": 0.04, "left": 0.06}),
            padding=dict(data.get("padding") or {"top": 0.02, "right": 0.02, "bottom": 0.02, "left": 0.02}),
            safe_areas=tuple(
                dict(x) for x in (data.get("safe_areas") or ()) if isinstance(x, dict)
            ),
            bleed=float(data.get("bleed") or 0.0),
            grid_columns=int(data.get("grid_columns") or 12),
            grid_gutter=float(data.get("grid_gutter") or 0.02),
            alignment_rules=dict(data.get("alignment_rules") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class ExportProfile:
    profile_id: str
    name: str = ""
    width: int = 1080
    height: int = 1350
    margins: dict[str, float] = field(default_factory=dict)
    safe_area: dict[str, Any] = field(default_factory=dict)
    render_strategy: str = "svg_html_playwright"
    formats: tuple[str, ...] = ("png", "pdf", "zip")
    bleed: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "margins": dict(self.margins),
            "safe_area": dict(self.safe_area),
            "render_strategy": self.render_strategy,
            "formats": list(self.formats),
            "bleed": self.bleed,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> ExportProfile:
        if not data:
            return ExportProfile(profile_id="linkedin")
        return ExportProfile(
            profile_id=str(data.get("profile_id") or "linkedin"),
            name=str(data.get("name") or ""),
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            margins=dict(data.get("margins") or {}),
            safe_area=dict(data.get("safe_area") or {}),
            render_strategy=str(data.get("render_strategy") or "svg_html_playwright"),
            formats=tuple(str(x) for x in (data.get("formats") or ("png", "pdf", "zip"))),
            bleed=float(data.get("bleed") or 0.0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class DeckOptimizationResult:
    visual_density: float = 0.0
    whitespace: float = 0.0
    consistency: float = 0.0
    balance: float = 0.0
    reading_order: float = 0.0

    def composite(self) -> float:
        vals = (
            self.visual_density,
            self.whitespace,
            self.consistency,
            self.balance,
            self.reading_order,
        )
        return round(sum(vals) / len(vals), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "visual_density": self.visual_density,
            "whitespace": self.whitespace,
            "consistency": self.consistency,
            "balance": self.balance,
            "reading_order": self.reading_order,
            "composite": self.composite(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DeckOptimizationResult:
        if not data:
            return DeckOptimizationResult()
        return DeckOptimizationResult(
            visual_density=float(data.get("visual_density") or 0.0),
            whitespace=float(data.get("whitespace") or 0.0),
            consistency=float(data.get("consistency") or 0.0),
            balance=float(data.get("balance") or 0.0),
            reading_order=float(data.get("reading_order") or 0.0),
        )


@dataclass(slots=True)
class DeckDefinitionSlide:
    slide_id: str
    index: int
    purpose: str
    title: str = ""
    svg_fragment: str = ""
    layer_refs: tuple[dict[str, Any], ...] = ()
    prev_slide_id: str | None = None
    next_slide_id: str | None = None
    transition_hint: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "index": self.index,
            "purpose": self.purpose,
            "title": self.title,
            "svg_fragment": self.svg_fragment,
            "layer_refs": list(self.layer_refs),
            "prev_slide_id": self.prev_slide_id,
            "next_slide_id": self.next_slide_id,
            "transition_hint": self.transition_hint,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DeckDefinitionSlide:
        if not data:
            return DeckDefinitionSlide(slide_id=new_id(), index=0, purpose="educational")
        return DeckDefinitionSlide(
            slide_id=str(data.get("slide_id") or new_id()),
            index=int(data.get("index") or 0),
            purpose=str(data.get("purpose") or "educational"),
            title=str(data.get("title") or ""),
            svg_fragment=str(data.get("svg_fragment") or ""),
            layer_refs=tuple(
                dict(x) for x in (data.get("layer_refs") or ()) if isinstance(x, dict)
            ),
            prev_slide_id=data.get("prev_slide_id"),
            next_slide_id=data.get("next_slide_id"),
            transition_hint=str(data.get("transition_hint") or "none"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class DeckDefinition:
    """Canonical source of truth for rendering — renderer consumes this only."""

    definition_id: str
    deck_id: str
    title: str = ""
    slides: tuple[DeckDefinitionSlide, ...] = ()
    layout_constraints: LayoutConstraints = field(default_factory=LayoutConstraints)
    export_profile_id: str = "linkedin"
    width: int = 1080
    height: int = 1350
    render_strategy: str = "svg_html_playwright"
    draft_id: str = ""
    typography_asset_ids: tuple[str, ...] = ()
    image_refs: tuple[str, ...] = ()
    version: int = 1
    optimization: DeckOptimizationResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "deck_id": self.deck_id,
            "title": self.title,
            "slides": [s.to_dict() for s in self.slides],
            "layout_constraints": self.layout_constraints.to_dict(),
            "export_profile_id": self.export_profile_id,
            "width": self.width,
            "height": self.height,
            "render_strategy": self.render_strategy,
            "draft_id": self.draft_id,
            "typography_asset_ids": list(self.typography_asset_ids),
            "image_refs": list(self.image_refs),
            "version": self.version,
            "optimization": self.optimization.to_dict() if self.optimization else None,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> DeckDefinition:
        if not data:
            return DeckDefinition(definition_id=new_id(), deck_id=new_id())
        return DeckDefinition(
            definition_id=str(data.get("definition_id") or new_id()),
            deck_id=str(data.get("deck_id") or new_id()),
            title=str(data.get("title") or ""),
            slides=tuple(
                DeckDefinitionSlide.from_dict(x)
                for x in (data.get("slides") or [])
                if isinstance(x, dict)
            ),
            layout_constraints=LayoutConstraints.from_dict(data.get("layout_constraints")),
            export_profile_id=str(data.get("export_profile_id") or "linkedin"),
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            render_strategy=str(data.get("render_strategy") or "svg_html_playwright"),
            draft_id=str(data.get("draft_id") or ""),
            typography_asset_ids=tuple(str(x) for x in (data.get("typography_asset_ids") or ())),
            image_refs=tuple(str(x) for x in (data.get("image_refs") or ())),
            version=int(data.get("version") or 1),
            optimization=DeckOptimizationResult.from_dict(data.get("optimization")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class DependencyNode:
    node_id: str
    kind: str  # draft | typography | carousel | export
    ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "ref": self.ref,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class DependencyEdge:
    parent_id: str
    child_id: str
    relation: str = "produces"

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "relation": self.relation,
        }


@dataclass(slots=True)
class AssetDependencyGraph:
    """Draft → Typography → Carousel → Export for replay/regeneration."""

    graph_id: str
    nodes: tuple[DependencyNode, ...] = ()
    edges: tuple[DependencyEdge, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> AssetDependencyGraph:
        if not data:
            return AssetDependencyGraph(graph_id=new_id())
        nodes = tuple(
            DependencyNode(
                node_id=str(x.get("node_id") or ""),
                kind=str(x.get("kind") or ""),
                ref=str(x.get("ref") or ""),
                metadata=dict(x.get("metadata") or {}),
            )
            for x in (data.get("nodes") or [])
            if isinstance(x, dict)
        )
        edges = tuple(
            DependencyEdge(
                parent_id=str(x.get("parent_id") or ""),
                child_id=str(x.get("child_id") or ""),
                relation=str(x.get("relation") or "produces"),
            )
            for x in (data.get("edges") or [])
            if isinstance(x, dict)
        )
        return AssetDependencyGraph(
            graph_id=str(data.get("graph_id") or new_id()),
            nodes=nodes,
            edges=edges,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class RenderPlan:
    width: int = 1080
    height: int = 1350
    strategy: str = "svg_html_playwright"
    optimize: bool = True
    scale: float = 1.0
    formats: tuple[str, ...] = ("svg", "png", "pdf")
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "strategy": self.strategy,
            "optimize": self.optimize,
            "scale": self.scale,
            "formats": list(self.formats),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> RenderPlan:
        if not data:
            return RenderPlan()
        return RenderPlan(
            width=int(data.get("width") or 1080),
            height=int(data.get("height") or 1350),
            strategy=str(data.get("strategy") or "svg_html_playwright"),
            optimize=bool(data.get("optimize", True)),
            scale=float(data.get("scale") or 1.0),
            formats=tuple(str(x) for x in (data.get("formats") or ("svg", "png", "pdf"))),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(slots=True)
class RenderedSlide:
    slide_id: str
    index: int
    svg: str
    png_bytes: bytes = b""
    html_shell: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "index": self.index,
            "svg": self.svg,
            "png_size": len(self.png_bytes),
            "html_shell": self.html_shell[:200] if self.html_shell else "",
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class RenderedDeck:
    deck_id: str
    slides: tuple[RenderedSlide, ...] = ()
    width: int = 1080
    height: int = 1350
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deck_id": self.deck_id,
            "slides": [s.to_dict() for s in self.slides],
            "width": self.width,
            "height": self.height,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ExportArtifact:
    artifact_id: str
    format: str  # png | pdf | zip | svg
    object_key: str = ""
    size_bytes: int = 0
    slide_index: int | None = None
    content: bytes = b""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "format": self.format,
            "object_key": self.object_key,
            "size_bytes": self.size_bytes or len(self.content),
            "slide_index": self.slide_index,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class CarouselAsset:
    asset_id: str
    deck: Deck
    rendered: RenderedDeck | None = None
    exports: tuple[ExportArtifact, ...] = ()
    deck_definition: DeckDefinition | None = None
    dependency_graph: AssetDependencyGraph | None = None
    optimization: DeckOptimizationResult | None = None
    export_profile: str = "linkedin"
    typography_asset_ids: tuple[str, ...] = ()
    image_refs: tuple[str, ...] = ()
    version: int = 1
    parent_asset_id: str | None = None
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "deck": self.deck.to_dict(),
            "rendered": self.rendered.to_dict() if self.rendered else None,
            "exports": [e.to_dict() for e in self.exports],
            "deck_definition": self.deck_definition.to_dict() if self.deck_definition else None,
            "dependency_graph": self.dependency_graph.to_dict() if self.dependency_graph else None,
            "optimization": self.optimization.to_dict() if self.optimization else None,
            "export_profile": self.export_profile,
            "typography_asset_ids": list(self.typography_asset_ids),
            "image_refs": list(self.image_refs),
            "version": self.version,
            "parent_asset_id": self.parent_asset_id,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class CarouselPipelineRequest:
    organization_id: str
    draft_id: str
    draft_snapshot: dict[str, Any] = field(default_factory=dict)
    typography_assets: tuple[dict[str, Any], ...] = ()
    image_refs: tuple[str, ...] = ()
    target_width: int = 1080
    target_height: int = 1350
    export_formats: tuple[str, ...] = ("png", "pdf", "zip")
    export_profile: str = "linkedin"
    correlation_id: str = ""
    replay_of_asset_id: str | None = None
    use_mock_renderer: bool = True


@dataclass(slots=True)
class CarouselPipelineResult:
    asset: CarouselAsset
    status: str
    plan: CarouselPlan | None = None
    render_plan: RenderPlan | None = None
    deck_definition: DeckDefinition | None = None
    optimization: DeckOptimizationResult | None = None
    dependency_graph: AssetDependencyGraph | None = None
    render_time_ms: int = 0
    export_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset.to_dict(),
            "status": self.status,
            "plan": self.plan.to_dict() if self.plan else None,
            "render_plan": self.render_plan.to_dict() if self.render_plan else None,
            "deck_definition": self.deck_definition.to_dict() if self.deck_definition else None,
            "optimization": self.optimization.to_dict() if self.optimization else None,
            "dependency_graph": self.dependency_graph.to_dict() if self.dependency_graph else None,
            "render_time_ms": self.render_time_ms,
            "export_time_ms": self.export_time_ms,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class CarouselReplayRecord:
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
class DeckDiff:
    left_deck_id: str
    right_deck_id: str
    slide_changes: dict[str, Any] = field(default_factory=dict)
    count_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_deck_id": self.left_deck_id,
            "right_deck_id": self.right_deck_id,
            "slide_changes": dict(self.slide_changes),
            "count_changed": self.count_changed,
        }


@dataclass(slots=True)
class SlideDiff:
    left_slide_id: str
    right_slide_id: str
    purpose_changed: bool = False
    title_changed: bool = False
    layer_changes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_slide_id": self.left_slide_id,
            "right_slide_id": self.right_slide_id,
            "purpose_changed": self.purpose_changed,
            "title_changed": self.title_changed,
            "layer_changes": dict(self.layer_changes),
        }
