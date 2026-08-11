"""Unit tests for M11r typography refinements — no M12 carousel/PDF."""

from __future__ import annotations

import asyncio

from app.modules.image.application.layout import DefaultLayoutPlanner
from app.modules.image.domain.models import CompositionPlan, EnrichedVisualBrief, ScenePlan
from app.modules.typography.application.brand_engine import DefaultBrandEngine
from app.modules.typography.application.design_tokens import DesignTokenEngine
from app.modules.typography.application.factory import TypographyFactory
from app.modules.typography.application.templates import LayoutTemplateRegistry
from app.modules.typography.domain.models import TypographyCopy, TypographyPipelineRequest


def _layout_plan(width: int = 1080, height: int = 1350) -> dict:
    brief = EnrichedVisualBrief(
        typography_safe_area="bottom_third",
        icons=("shield",),
        negative_prompt="text, watermark",
    )
    scene = ScenePlan(icons=("shield",))
    composition = CompositionPlan(width=width, height=height)
    return DefaultLayoutPlanner().plan(
        brief=brief, scene=scene, composition=composition, image_width=width, image_height=height
    ).to_dict()


def _kit() -> dict:
    return {
        "name": "GuardIQ",
        "primary_color": "#0A1F2B",
        "accent_color": "#1A5CB0",
        "font_heading": "Inter",
        "font_body": "Inter",
        "footer_text": "Guardiq",
    }


def test_design_tokens_include_expanded_groups() -> None:
    tokens = DesignTokenEngine().resolve(variant="dark", brand_kit=_kit())
    for key in ("spacing", "radius", "elevation", "shadows", "borders", "opacity", "animation"):
        assert getattr(tokens, key), f"missing {key}"
    assert tokens.typography.get("scale")
    assert tokens.colors.get("text_primary")
    brand = DefaultBrandEngine().apply(_kit(), variant="dark")
    assert brand.design_tokens is not None
    assert brand.design_tokens.spacing.get("md") == 16


def test_slide_composition_metadata_no_carousel_side_effects() -> None:
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        result = await eng.run(
            TypographyPipelineRequest(
                organization_id="org1",
                draft_id="d1",
                layout_plan=_layout_plan(),
                brand_kit=_kit(),
                copy=TypographyCopy(
                    headline="Stop invoice fraud before it hits finance",
                    subtitle="A practical checklist for BEC and payment diversion controls across AP workflows",
                    cta="Follow for more",
                ),
                template_id="checklist",
            )
        )
        assert result.status == "completed"
        assert result.slide_composition is not None
        assert result.asset.slide_composition is not None
        sc = result.slide_composition
        assert sc.preferred_slide_type == "checklist"
        assert sc.preferred_layout == "checklist"
        assert sc.metadata.get("renders_carousel") is False
        assert "carousel" not in result.asset.svg.lower()
        assert (
            result.asset.metadata.get("slide_composition", {})
            .get("metadata", {})
            .get("renders_carousel")
            is False
        )

    asyncio.run(_run())


def test_typography_intelligence_independent_scores() -> None:
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        result = await eng.run(
            TypographyPipelineRequest(
                organization_id="org1",
                draft_id="d1",
                layout_plan=_layout_plan(),
                brand_kit=_kit(),
                copy=TypographyCopy(headline="Short hook", subtitle="Body", cta="CTA"),
            )
        )
        intel = result.intelligence
        assert intel is not None
        assert 0.0 <= intel.readability <= 1.0
        assert 0.0 <= intel.scanability <= 1.0
        assert 0.0 <= intel.density <= 1.0
        assert 0.0 <= intel.hierarchy <= 1.0
        assert 0.0 <= intel.whitespace <= 1.0
        assert "composite" in intel.to_dict()
        # Distinct from overlay a11y fields
        assert result.asset.overlay_validation is not None
        assert "accessibility_score" not in intel.to_dict()

    asyncio.run(_run())


def test_each_template_loads_and_affects_plan_metadata() -> None:
    registry = LayoutTemplateRegistry()
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        for tid in registry.list_ids():
            tmpl = registry.get(tid)
            assert tmpl.template_id == tid or tid == "default"
            assert tmpl.layer_order
            result = await eng.run(
                TypographyPipelineRequest(
                    organization_id="org1",
                    draft_id=f"d-{tid}",
                    layout_plan=_layout_plan(),
                    brand_kit=_kit(),
                    copy=TypographyCopy(headline=f"Title {tid}", subtitle="Sub", cta="Go"),
                    template_id=tid,
                )
            )
            assert result.status == "completed"
            plan = result.asset.typography_plan
            assert plan is not None
            assert plan.template_id == tid
            assert plan.metadata.get("layer_order") == list(tmpl.layer_order)
            assert result.asset.metadata.get("template_id") == tid
            assert result.slide_composition is not None
            assert result.slide_composition.preferred_layout == tmpl.preferred_layout

    asyncio.run(_run())


def test_svg_layer_exposes_rich_metadata() -> None:
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        result = await eng.run(
            TypographyPipelineRequest(
                organization_id="org1",
                draft_id="d1",
                layout_plan=_layout_plan(),
                brand_kit=_kit(),
                copy=TypographyCopy(headline="Layered title", subtitle="Sub", cta="CTA"),
            )
        )
        assert result.asset.layers
        for layer in result.asset.layers:
            d = layer.to_dict()
            assert "id" in d and d["id"] == layer.layer_id
            assert "parent" in d
            assert "constraints" in d
            assert "z_index" in d
            assert "anchor" in d
            assert "visibility" in d
            assert "animation" in d
            assert layer.visibility == "visible"

    asyncio.run(_run())
