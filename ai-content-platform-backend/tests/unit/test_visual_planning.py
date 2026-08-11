"""Visual Pattern Engine, story, quality, and golden prompt tests."""

from __future__ import annotations

from app.modules.image.application.content_subject import (
    build_content_subject,
    inject_content_into_brief,
)
from app.modules.image.application.prompt_builder import DefaultImagePromptBuilder
from app.modules.image.application.visual_pattern_engine import VisualPatternEngine
from app.modules.image.application.visual_planning import plan_visual
from app.modules.image.domain.models import CompositionPlan, EnrichedVisualBrief, ScenePlan


NOISE_HOOK = "Not every headline impacts your practice."
NOISE_BODY = (
    "We're constantly sifting through global news to find what genuinely matters "
    "for UK care, legal, and accountancy practices. "
    "Today, we saw an appeals court in Texas rejected an effort to overturn a gun ban "
    "at the State Fair. This followed a shooting there in 2024. "
    "While significant news in its own context, this specific legal decision in the US "
    "doesn't directly affect the IT security of your business here in the UK. "
    "What does matter? The latest CQC guidance and SRA updates. "
    "Filtering out the noise is the real challenge."
)


def test_pattern_engine_selects_decision_funnel_for_noise_post() -> None:
    engine = VisualPatternEngine()
    intent = engine.detect_intent(
        hook=NOISE_HOOK, body=NOISE_BODY, content_type="educational"
    )
    assert intent in {"explainer", "educational"}
    pattern = engine.select(
        intent=intent, legacy_visual_mode="signal_filter", message={"pain_point": "news overload"}
    )
    assert pattern["id"] == "decision_funnel"
    assert "funnel" in str(pattern.get("prompt_focus") or "").lower()


def test_plan_visual_scores_and_tokens() -> None:
    plan = plan_visual(
        hook=NOISE_HOOK,
        body=NOISE_BODY,
        content_type="educational",
        legacy_visual_mode="signal_filter",
        short_labels="Compliance risk; UK regulation",
        brand={"primary_color": "#0A1F2B", "accent_color": "#1A5CB0", "name": "Guard IQ"},
    )
    assert plan["pattern_id"] == "decision_funnel"
    assert plan["post_intent"] in {"explainer", "educational"}
    assert plan["message"]["primary_message"]
    assert plan["story"]["beats"]
    assert plan["design_tokens"]["icon_style"]
    assert plan["design_tokens"]["style_targets"]
    assert plan["quality"]["overall"] >= plan["quality"]["threshold"] or plan["quality"].get(
        "upgraded"
    )
    assert "robots" in plan["always_avoid"] or "robots" in str(plan["always_avoid"])


def test_noise_filter_labels_and_inject_plan() -> None:
    subject = build_content_subject(
        hook=NOISE_HOOK, body=NOISE_BODY, content_type="educational"
    )
    assert subject["visual_mode"] == "signal_filter"
    assert "Compliance risk" in subject["short_labels"]
    assert "UK regulation" in subject["short_labels"]

    brief = inject_content_into_brief(
        {},
        hook=NOISE_HOOK,
        body=NOISE_BODY,
        content_type="educational",
        brand_palette=["#0A1F2B", "#FFFFFF", "#1A5CB0"],
        brand={"name": "Guard IQ", "primary_color": "#0A1F2B"},
    )
    meta = brief["metadata"]
    assert meta["visual_pattern_id"] == "decision_funnel"
    assert meta["visual_plan"]["pattern_id"] == "decision_funnel"
    assert "funnel" in brief["scene"].lower()
    assert "stripe" in brief["scene"].lower() or "cloudflare" in brief["scene"].lower()
    assert "no watermark" in brief["negative_prompt"].lower()
    assert meta.get("visual_quality_score") is not None


def test_golden_prompt_contains_designer_clauses() -> None:
    brief_dict = inject_content_into_brief(
        {},
        hook=NOISE_HOOK,
        body=NOISE_BODY,
        content_type="educational",
        brand={"primary_color": "#0A1F2B", "accent_color": "#1A5CB0"},
        brand_palette=["#0A1F2B", "#FFFFFF", "#1A5CB0"],
    )
    brief = EnrichedVisualBrief(
        illustration_style=brief_dict.get("illustration_style") or "educational_infographic",
        theme="professional",
        purpose="educate",
        audience="uk",
        visual_tone="calm",
        typography_safe_area="bottom_third",
        negative_prompt=brief_dict.get("negative_prompt") or "",
        color_palette=tuple(brief_dict.get("color_palette") or ()),
        brand_direction="Guard IQ",
        image_intent="inform",
        scene_hint=brief_dict.get("scene_hint") or "",
        metadata=brief_dict.get("metadata") or {},
    )
    scene = ScenePlan(
        layout="educational_infographic",
        foreground=("funnel",),
        background=("soft_off_white",),
        icons=("funnel", "target"),
    )
    composition = CompositionPlan(
        width=1080, height=1080, balance="centered", camera="eye", focus="funnel"
    )
    req = DefaultImagePromptBuilder().build(
        brief,
        scene,
        composition,
        brand={"name": "Guard IQ", "primary_color": "#0A1F2B", "accent_color": "#1A5CB0"},
    )
    p = req.positive_prompt.lower()
    assert "premium linkedin" in p or "editorial" in p
    assert "funnel" in p
    assert "compliance risk" in p
    assert "whitespace" in p or "white space" in p or "typography-safe" in p
    assert "robot" in p  # avoidance clause
    assert "#0a1f2b" in p
    assert "generate a cybersecurity image" not in p
    assert req.metadata.get("visual_pattern_id") == "decision_funnel"


def test_legacy_mode_maps_big_stat() -> None:
    engine = VisualPatternEngine()
    pattern = engine.select(intent="educational", legacy_visual_mode="big_stat")
    assert pattern["id"] == "key_statistics"
