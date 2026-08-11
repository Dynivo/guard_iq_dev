"""DeckDefinition builder — canonical SoT assembled after DeckBuilder."""

from __future__ import annotations

from pathlib import Path

from app.modules.carousel.application.export_profiles import ExportProfileRegistry
from app.modules.carousel.domain.models import (
    Deck,
    DeckDefinition,
    DeckDefinitionSlide,
    LayoutConstraints,
    new_id,
)


class DefaultDeckDefinitionBuilder:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._profiles = ExportProfileRegistry(config_dir)

    def build(
        self,
        deck: Deck,
        *,
        draft_id: str = "",
        typography_asset_ids: tuple[str, ...] = (),
        image_refs: tuple[str, ...] = (),
        export_profile_id: str = "linkedin",
        width: int | None = None,
        height: int | None = None,
        extra_safe_areas: tuple[dict, ...] = (),
    ) -> DeckDefinition:
        profile = self._profiles.get(export_profile_id)
        constraints = self._profiles.layout_constraints(export_profile_id)
        if extra_safe_areas:
            constraints = LayoutConstraints(
                margins=constraints.margins,
                padding=constraints.padding,
                safe_areas=constraints.safe_areas + tuple(extra_safe_areas),
                bleed=constraints.bleed,
                grid_columns=constraints.grid_columns,
                grid_gutter=constraints.grid_gutter,
                alignment_rules=constraints.alignment_rules,
                metadata={**constraints.metadata, "merged_composition_safe_areas": True},
            )

        slides: list[DeckDefinitionSlide] = []
        for slide in deck.slides:
            svg = ""
            layer_refs: list[dict] = []
            if slide.composition:
                svg = slide.composition.svg_fragment
                layer_refs = [L.to_dict() for L in slide.composition.layers]
            slides.append(
                DeckDefinitionSlide(
                    slide_id=slide.slide_id,
                    index=slide.index,
                    purpose=slide.purpose,
                    title=slide.title,
                    svg_fragment=svg,
                    layer_refs=tuple(layer_refs),
                    prev_slide_id=slide.prev_slide_id,
                    next_slide_id=slide.next_slide_id,
                    transition_hint=slide.transition_hint,
                    metadata={
                        "preferred_layout": (slide.metadata or {}).get("preferred_layout"),
                        "body_chars": len(slide.body or ""),
                    },
                )
            )

        return DeckDefinition(
            definition_id=new_id(),
            deck_id=deck.deck_id,
            title=deck.title,
            slides=tuple(slides),
            layout_constraints=constraints,
            export_profile_id=profile.profile_id,
            width=int(width if width is not None else profile.width),
            height=int(height if height is not None else profile.height),
            render_strategy=profile.render_strategy,
            draft_id=draft_id,
            typography_asset_ids=typography_asset_ids,
            image_refs=image_refs,
            version=deck.version,
            metadata={
                "canonical_sot": True,
                "slide_count": len(slides),
                "mutates_content": False,
            },
        )
