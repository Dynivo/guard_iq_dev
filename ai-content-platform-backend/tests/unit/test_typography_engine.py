"""Unit tests for M11 Brand & Typography Engine."""

from __future__ import annotations

import asyncio

from app.modules.image.application.layout import DefaultLayoutPlanner
from app.modules.image.domain.models import CompositionPlan, EnrichedVisualBrief, ScenePlan
from app.modules.typography.application.brand_engine import DefaultBrandEngine
from app.modules.typography.application.factory import TypographyFactory
from app.modules.typography.application.layout_enrich import DefaultLayoutEnricher
from app.modules.typography.domain.models import TypographyCopy, TypographyPipelineRequest
from app.modules.workflow.application.factory import WorkflowFactory


def _layout_plan(width: int = 1080, height: int = 1350) -> dict:
    brief = EnrichedVisualBrief(
        typography_safe_area="bottom_third",
        icons=("shield", "invoice"),
        negative_prompt="text, watermark",
    )
    scene = ScenePlan(icons=("shield", "invoice"))
    composition = CompositionPlan(width=width, height=height)
    return DefaultLayoutPlanner().plan(
        brief=brief, scene=scene, composition=composition, image_width=width, image_height=height
    ).to_dict()


def test_layout_enrich_never_renders_text() -> None:
    enriched = DefaultLayoutEnricher().enrich(_layout_plan(), width=1080, height=1350)
    assert enriched.grid_columns == 12
    assert enriched.safe_overlay_zones
    assert enriched.metadata.get("never_renders_text") is True


def test_brand_engine_from_kit_and_tokens() -> None:
    brand = DefaultBrandEngine().apply(
        {
            "id": "b1",
            "name": "GuardIQ",
            "primary_color": "#0A1F2B",
            "accent_color": "#1A5CB0",
            "font_heading": "Inter",
            "font_body": "Inter",
            "footer_text": "Guardiq Security",
        },
        variant="dark",
    )
    assert brand.brand_name == "GuardIQ"
    assert brand.text_color.startswith("#")
    assert "allowed_fonts" in brand.metadata


def test_svg_renderer_layers_and_no_early_raster() -> None:
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        result = await eng.run(
            TypographyPipelineRequest(
                organization_id="org1",
                draft_id="d1",
                layout_plan=_layout_plan(),
                brand_kit={
                    "name": "GuardIQ",
                    "primary_color": "#0A1F2B",
                    "accent_color": "#1A5CB0",
                    "font_heading": "Inter",
                    "font_body": "Inter",
                    "footer_text": "Guardiq",
                },
                copy=TypographyCopy(
                    headline="Stop invoice fraud",
                    subtitle="Practical BEC controls",
                    cta="Follow for more",
                    footer="Guardiq",
                ),
                illustration_ref="asset://illustration.png",
            )
        )
        assert result.status == "completed"
        asset = result.asset
        assert "<svg" in asset.svg
        assert any(layer.kind == "text" for layer in asset.layers)
        assert any(layer.metadata.get("vector_text") for layer in asset.layers if layer.kind == "text")
        assert asset.metadata.get("primary_format") == "svg"
        # Not a flattened PNG primary
        assert not asset.svg.startswith(b"\x89PNG".decode("latin1", errors="ignore")[:1] + "PNG")
        assert asset.overlay_validation and asset.overlay_validation.passed
        assert asset.brand_validation and asset.brand_validation.passed

    asyncio.run(_run())


def test_multi_size_scaling() -> None:
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        square = await eng.run(
            TypographyPipelineRequest(
                organization_id="org1",
                draft_id="d1",
                layout_plan=_layout_plan(1080, 1080),
                brand_kit={"name": "Brand", "primary_color": "#0A1F2B", "accent_color": "#1A5CB0", "font_heading": "Inter", "font_body": "Inter"},
                copy=TypographyCopy(headline="Square format", cta="Learn more"),
                target_width=1080,
                target_height=1080,
            )
        )
        assert square.status == "completed"
        assert square.asset.height == 1080

    asyncio.run(_run())


def test_overlay_diff_and_replay() -> None:
    async def _run() -> None:
        eng = TypographyFactory.create_memory()
        req = TypographyPipelineRequest(
            organization_id="org1",
            draft_id="d1",
            layout_plan=_layout_plan(),
            brand_kit={"name": "Brand", "primary_color": "#0A1F2B", "accent_color": "#1A5CB0", "font_heading": "Inter", "font_body": "Inter"},
            copy=TypographyCopy(headline="One", cta="Go"),
        )
        a = await eng.run(req)
        assert a.status == "completed"
        replay_id = next(iter(eng.replay_store._items))
        b = await eng.replay(replay_id)
        assert b.status == "completed"
        diff = eng.diff_service.diff(a.asset, b.asset)
        assert diff.left_asset_id != diff.right_asset_id

    asyncio.run(_run())


def test_typography_workflow_nodes_registered() -> None:
    _, _, nodes = WorkflowFactory.create(load_builtins=True)
    for name in (
        "layout.plan",
        "typography.plan",
        "brand.apply",
        "typography.render",
        "overlay.validate",
        "brand.validate",
        "typography.store",
    ):
        assert nodes.get(name) is not None
