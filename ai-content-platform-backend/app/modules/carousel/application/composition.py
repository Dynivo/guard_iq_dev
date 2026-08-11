"""Slide composition — arrange existing typography/image layers; never renders."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from app.modules.carousel.application.config_loader import load_carousel
from app.modules.carousel.domain.models import (
    CarouselPlan,
    ComposedLayerRef,
    SlideComposition,
)


class DefaultSlideCompositionEngine:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_carousel("composition.yaml", config_dir)

    def compose(
        self,
        plan: CarouselPlan,
        *,
        typography_assets: tuple[dict[str, Any], ...] = (),
        image_refs: tuple[str, ...] = (),
    ) -> tuple[SlideComposition, ...]:
        assets_by_id = {
            str(a.get("asset_id")): a for a in typography_assets if a.get("asset_id")
        }
        default_asset = typography_assets[0] if typography_assets else {}
        results: list[SlideComposition] = []
        for slide in plan.slides:
            asset = assets_by_id.get(str(slide.typography_asset_id or "")) or default_asset
            layers = self._layer_refs(asset)
            svg = self._svg_fragment(slide.title, slide.body, asset, slide.image_ref or (image_refs[0] if image_refs else ""))
            layout = asset.get("layout") or {}
            safe = []
            if isinstance(layout, dict):
                safe = list(layout.get("safe_overlay_zones") or ())
            results.append(
                SlideComposition(
                    slide_index=slide.index,
                    purpose=slide.purpose,
                    layers=layers,
                    grid_columns=int(self._cfg.get("grid_columns") or 12),
                    safe_areas=tuple(dict(x) for x in safe if isinstance(x, dict)),
                    visual_balance=float(self._cfg.get("default_balance") or 0.55),
                    whitespace_score=float(self._cfg.get("default_whitespace") or 0.6),
                    alignment="left",
                    svg_fragment=svg,
                    metadata={
                        "preferred_layout": slide.preferred_layout,
                        "renders": False,
                        "mutates_typography": False,
                        "typography_asset_id": asset.get("asset_id"),
                    },
                )
            )
        return tuple(results)

    def _layer_refs(self, asset: dict[str, Any]) -> tuple[ComposedLayerRef, ...]:
        priority = list(self._cfg.get("layer_source_priority") or [])
        raw_layers = asset.get("layers") or []
        refs: list[ComposedLayerRef] = []
        for layer in raw_layers:
            if not isinstance(layer, dict):
                continue
            role = str(layer.get("role") or "")
            refs.append(
                ComposedLayerRef(
                    layer_id=str(layer.get("layer_id") or layer.get("id") or role),
                    role=role,
                    kind=str(layer.get("kind") or "text"),
                    source="typography",
                    z_index=int(layer.get("z_index") or 0),
                    anchor=str(layer.get("anchor") or "top_left"),
                    visibility=str(layer.get("visibility") or "visible"),
                    metadata={"copied": True, "mutated": False},
                )
            )
        # Stable order by priority then z_index
        def sort_key(ref: ComposedLayerRef) -> tuple[int, int]:
            try:
                p = priority.index(ref.role.split("_")[0] if ref.role.startswith("icon_") else ref.role)
            except ValueError:
                p = 99
            return (p, ref.z_index)

        refs.sort(key=sort_key)
        return tuple(refs)

    def _svg_fragment(
        self,
        title: str,
        body: str,
        asset: dict[str, Any],
        image_ref: str,
    ) -> str:
        """Compose SVG without rewriting typography rules — prefer asset SVG when present."""
        source_svg = str(asset.get("svg") or "").strip()
        if source_svg and "<svg" in source_svg:
            # Annotate with slide title as metadata comment only — do not alter text nodes
            safe_title = html.escape(title[:80])
            if source_svg.startswith("<?xml"):
                return f"<!-- carousel_slide title={safe_title} -->\n{source_svg}"
            return f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- carousel_slide title={safe_title} -->\n{source_svg}'

        # Fallback compose from title/body + illustration ref (still no brand re-application)
        w = int((asset.get("width") or 1080))
        h = int((asset.get("height") or 1350))
        img = ""
        if image_ref:
            img = (
                f'<image href="{html.escape(image_ref)}" x="0" y="0" '
                f'width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/>'
            )
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f"{img}"
            f'<text x="80" y="{int(h * 0.72)}" font-size="48" fill="#FFFFFF">'
            f"{html.escape(title[:90])}</text>"
            f'<text x="80" y="{int(h * 0.82)}" font-size="28" fill="#C5D5E0">'
            f"{html.escape(body[:140])}</text>"
            f"</svg>"
        )
