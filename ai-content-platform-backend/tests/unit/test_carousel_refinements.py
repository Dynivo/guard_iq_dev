"""Unit tests for M12r carousel refinements — no M13."""

from __future__ import annotations

import asyncio
import copy
import inspect

from app.modules.carousel.application.export_profiles import ExportProfileRegistry
from app.modules.carousel.application.factory import CarouselFactory
from app.modules.carousel.application.renderer import MockCarouselRenderer
from app.modules.carousel.domain.models import CarouselPipelineRequest
from app.modules.workflow.application.factory import WorkflowFactory


def _typo_asset(asset_id: str = "typo-1") -> dict:
    return {
        "asset_id": asset_id,
        "svg": '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350">'
        '<text x="10" y="40">Brand Title</text></svg>',
        "layers": [
            {
                "layer_id": "title-1",
                "role": "title",
                "kind": "text",
                "z_index": 20,
                "anchor": "top_left",
                "visibility": "visible",
            }
        ],
        "width": 1080,
        "height": 1350,
        "slide_composition": {
            "preferred_layout": "hero",
            "transition_hint": "fade",
        },
        "illustration_ref": "asset://illustration.png",
        "layout": {"safe_overlay_zones": [{"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.2}]},
    }


def test_renderer_accepts_deck_definition_only() -> None:
    sig = inspect.signature(MockCarouselRenderer.render)
    params = list(sig.parameters)
    assert params == ["self", "definition"]
    assert "deck" not in params
    assert "render_plan" not in params


def test_deck_definition_has_layout_constraints_and_optimizer() -> None:
    async def _run() -> None:
        eng = CarouselFactory.create_memory()
        draft = {
            "hook": "Hook",
            "cta": "CTA",
            "generated_text": "A.\n\nB.\n\nC.",
        }
        draft_copy = copy.deepcopy(draft)
        typo = _typo_asset()
        typo_copy = copy.deepcopy(typo)
        result = await eng.run(
            CarouselPipelineRequest(
                organization_id="org",
                draft_id="draft-1",
                draft_snapshot=draft,
                typography_assets=(typo,),
                export_profile="linkedin",
                use_mock_renderer=True,
            )
        )
        assert result.status == "completed"
        assert draft == draft_copy
        assert typo == typo_copy
        assert result.deck_definition is not None
        assert result.asset.deck_definition is not None
        lc = result.deck_definition.layout_constraints
        assert lc.margins
        assert lc.padding
        assert lc.grid_columns >= 1
        assert "alignment_rules" in lc.to_dict()
        assert result.optimization is not None
        d = result.optimization.to_dict()
        for key in ("visual_density", "whitespace", "consistency", "balance", "reading_order"):
            assert 0.0 <= d[key] <= 1.0
        assert "composite" in d
        assert result.asset.metadata.get("editable_sot") == "deck_definition"

    asyncio.run(_run())


def test_dependency_graph_links_draft_typography_carousel_export() -> None:
    async def _run() -> None:
        eng = CarouselFactory.create_memory()
        result = await eng.run(
            CarouselPipelineRequest(
                organization_id="org",
                draft_id="draft-dep",
                draft_snapshot={"hook": "H", "cta": "C", "generated_text": "1.\n\n2.\n\n3."},
                typography_assets=(_typo_asset("typo-dep"),),
                use_mock_renderer=True,
            )
        )
        graph = result.dependency_graph
        assert graph is not None
        kinds = {n.kind for n in graph.nodes}
        assert "draft" in kinds
        assert "typography" in kinds
        assert "carousel" in kinds
        assert "export" in kinds
        assert any(e.relation == "produces" for e in graph.edges)
        assert graph.metadata.get("supports_replay") is True

    asyncio.run(_run())


def test_each_export_profile_loads() -> None:
    registry = ExportProfileRegistry()
    for pid in registry.list_ids():
        profile = registry.get(pid)
        assert profile.profile_id == pid
        assert profile.width > 0 and profile.height > 0
        assert profile.margins
        assert profile.safe_area
        assert profile.render_strategy
        constraints = registry.layout_constraints(pid)
        assert constraints.margins
        assert constraints.safe_areas or profile.safe_area


def test_profiles_affect_definition_size() -> None:
    async def _run() -> None:
        eng = CarouselFactory.create_memory()
        ig = await eng.run(
            CarouselPipelineRequest(
                organization_id="org",
                draft_id="d-ig",
                draft_snapshot={"hook": "H", "cta": "C", "generated_text": "1.\n\n2.\n\n3."},
                typography_assets=(_typo_asset(),),
                export_profile="instagram",
                use_mock_renderer=True,
            )
        )
        assert ig.deck_definition is not None
        assert ig.deck_definition.width == 1080
        assert ig.deck_definition.height == 1080
        assert ig.asset.export_profile == "instagram"

    asyncio.run(_run())


def test_optimize_handler_registered() -> None:
    _, _, nodes = WorkflowFactory.create(load_builtins=True)
    assert nodes.get("carousel.optimize") is not None
    assert nodes.get("carousel.render") is not None
