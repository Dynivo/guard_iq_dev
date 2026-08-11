"""Unit tests for M12 Carousel Composition & Rendering Engine."""

from __future__ import annotations

import asyncio
import copy

from app.modules.carousel.application.factory import CarouselFactory
from app.modules.carousel.application.planner import DefaultCarouselPlanner
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
            "preferred_slide_type": "hero",
            "preferred_layout": "hero",
            "transition_hint": "fade",
            "continuation_hint": "none",
        },
        "illustration_ref": "asset://illustration.png",
    }


def test_planner_uses_draft_carousel_no_llm() -> None:
    plan = DefaultCarouselPlanner().plan(
        {
            "hook": "Hook",
            "cta": "CTA",
            "carousel": {
                "slides": [
                    {"role": "hook", "title": "A", "body": "a"},
                    {"role": "problem", "title": "B", "body": "b"},
                    {"role": "solution", "title": "C", "body": "c"},
                    {"role": "cta", "title": "D", "body": "d"},
                ]
            },
        },
        typography_assets=(_typo_asset(),),
    )
    assert plan.slide_count >= 3
    assert plan.metadata.get("uses_llm") is False
    assert "hook" in plan.sequence


def test_engine_composes_without_mutating_draft_or_typography() -> None:
    async def _run() -> None:
        eng = CarouselFactory.create_memory(use_mock_renderer=True)
        draft = {
            "hook": "Stop invoice fraud",
            "cta": "Follow for more",
            "generated_text": "Para one.\n\nPara two.\n\nPara three.",
            "carousel": {
                "slides": [
                    {"role": "hook", "title": "Stop fraud", "body": "Intro"},
                    {"role": "problem", "title": "BEC risk", "body": "Problem"},
                    {"role": "solution", "title": "Controls", "body": "Solution"},
                    {"role": "cta", "title": "Follow", "body": "CTA"},
                ]
            },
        }
        draft_copy = copy.deepcopy(draft)
        typo = _typo_asset()
        typo_copy = copy.deepcopy(typo)
        result = await eng.run(
            CarouselPipelineRequest(
                organization_id="org1",
                draft_id="d1",
                draft_snapshot=draft,
                typography_assets=(typo,),
                image_refs=("asset://illustration.png",),
                use_mock_renderer=True,
            )
        )
        assert result.status == "completed"
        assert draft == draft_copy
        assert typo == typo_copy
        assert result.asset.metadata.get("mutates_draft") is False
        assert result.asset.metadata.get("mutates_typography") is False
        assert result.asset.metadata.get("calls_llm") is False
        assert result.asset.metadata.get("calls_image_model") is False
        assert result.asset.metadata.get("editable_sot") == "deck_definition"
        assert result.asset.rendered is not None
        assert all("<svg" in s.svg for s in result.asset.rendered.slides)
        formats = {e.format for e in result.asset.exports}
        assert "svg" in formats
        assert "png" in formats
        assert "pdf" in formats
        assert "zip" in formats
        assert all(e.content for e in result.asset.exports if e.format in ("png", "pdf", "zip", "svg"))

    asyncio.run(_run())


def test_composition_does_not_render_flag() -> None:
    async def _run() -> None:
        eng = CarouselFactory.create_memory()
        plan = eng._planner.plan(
            {"hook": "H", "cta": "C", "generated_text": "One.\n\nTwo.\n\nThree."},
            typography_assets=(_typo_asset(),),
        )
        comps = eng._composer.compose(plan, typography_assets=(_typo_asset(),))
        assert comps
        assert all(c.metadata.get("renders") is False for c in comps)
        assert all(c.metadata.get("mutates_typography") is False for c in comps)
        deck = eng._deck.build(plan, comps, title="T")
        assert len(deck.slides) == len(plan.slides)
        assert deck.slides[0].next_slide_id is not None or len(deck.slides) == 1

    asyncio.run(_run())


def test_deck_diff_and_replay() -> None:
    async def _run() -> None:
        eng = CarouselFactory.create_memory()
        req = CarouselPipelineRequest(
            organization_id="org1",
            draft_id="d1",
            draft_snapshot={
                "hook": "Hook",
                "cta": "CTA",
                "generated_text": "A.\n\nB.\n\nC.",
            },
            typography_assets=(_typo_asset(),),
            use_mock_renderer=True,
        )
        first = await eng.run(req)
        records = list(eng.replay_store._items.values())
        assert records
        second = await eng.replay(records[0].replay_id)
        assert second.status == "completed"
        diff = eng.diff_service.diff_decks(first.asset.deck, second.asset.deck)
        assert diff.left_deck_id == first.asset.deck.deck_id

    asyncio.run(_run())


def test_carousel_workflow_handlers_registered() -> None:
    _, _, nodes = WorkflowFactory.create(load_builtins=True)
    for node_type in (
        "carousel.plan",
        "carousel.compose",
        "carousel.build",
        "carousel.render",
        "carousel.export",
        "carousel.store",
        "carousel.pipeline",
    ):
        assert nodes.get(node_type) is not None
