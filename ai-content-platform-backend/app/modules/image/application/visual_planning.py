"""Visual planning facade — Brand + Intent + Pattern + Story + Quality → plan dict.

Does not call image models. Safe to invoke from content grounding / brief inject.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.application.message_extractor import extract_message
from app.modules.image.application.visual_pattern_engine import VisualPatternEngine
from app.modules.image.application.visual_quality import score_visual_plan
from app.modules.image.application.visual_story import build_visual_story


# LinkedIn surface types → layout strategy hints (configurable overlay)
_LINKEDIN_TYPE_HINTS: dict[str, str] = {
    "single_post": "square_1x1_editorial_infographic",
    "carousel_cover": "bold_cover_metaphor_large_whitespace",
    "carousel_body": "one_idea_per_slide_cards",
    "announcement": "key_stat_or_badge_center",
    "statistics": "key_statistics_hero_numeral",
    "comparison": "split_panels",
    "quote": "quote_safe_margin_minimal_diagram",
    "framework": "connected_nodes_or_pillars",
    "checklist": "vertical_checklist_cards",
    "timeline": "horizontal_timeline",
    "case_study": "before_after_or_outcome_nodes",
    "warning": "warning_card_risk_meter",
}


def plan_visual(
    *,
    hook: str = "",
    body: str = "",
    cta: str = "",
    content_type: str = "",
    legacy_visual_mode: str = "",
    short_labels: str = "",
    brand: dict[str, Any] | None = None,
    linkedin_image_type: str = "single_post",
    variant_index: int = 0,
    audience_hint: str = "",
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """Full planning pass used by inject_content_into_brief."""
    brand = brand or {}
    tokens = load_yaml("design_tokens.yaml", config_dir)
    engine = VisualPatternEngine(config_dir)

    message = extract_message(
        hook=hook,
        body=body,
        cta=cta,
        content_type=content_type,
        audience_hint=audience_hint or str(brand.get("audience") or ""),
    )
    intent = engine.detect_intent(
        hook=hook, body=body, content_type=content_type, message=message
    )
    pattern = engine.select(
        intent=intent,
        legacy_visual_mode=legacy_visual_mode,
        message=message,
        variant_index=variant_index,
    )
    story = build_visual_story(
        pattern=pattern, message=message, short_labels=short_labels
    )
    quality = score_visual_plan(
        pattern=pattern,
        message=message,
        story=story,
        design_tokens=tokens,
        brand=brand,
        config_dir=config_dir,
    )

    # Soft upgrade: if planning score fails, switch pattern once (still generate)
    if not quality["passes"] and quality.get("upgrade_fallback_pattern"):
        fallback_id = str(quality["upgrade_fallback_pattern"])
        catalog = load_yaml("visual_patterns.yaml", config_dir).get("patterns") or {}
        if fallback_id in catalog and fallback_id != pattern.get("id"):
            pattern = dict(catalog[fallback_id])
            pattern["id"] = fallback_id
            pattern["intent"] = intent
            pattern["always_avoid"] = list(
                load_yaml("visual_patterns.yaml", config_dir).get("always_avoid") or []
            )
            story = build_visual_story(
                pattern=pattern, message=message, short_labels=short_labels
            )
            quality = score_visual_plan(
                pattern=pattern,
                message=message,
                story=story,
                design_tokens=tokens,
                brand=brand,
                config_dir=config_dir,
            )
            quality["upgraded"] = True

    style_targets = list(tokens.get("style_targets") or [])
    typo = tokens.get("typography_safe") or {}
    li_type = (linkedin_image_type or "single_post").strip().lower()
    layout_strategy = _LINKEDIN_TYPE_HINTS.get(li_type, _LINKEDIN_TYPE_HINTS["single_post"])

    brand_personality = str(
        brand.get("personality")
        or brand.get("voice")
        or brand.get("tone")
        or "calm expert MSP / cybersecurity advisor"
    )
    design_style = str(
        brand.get("design_style")
        or tokens.get("illustration_style")
        or "flat_vector_premium_saas"
    )

    return {
        "post_intent": intent,
        "message": message,
        "pattern_id": pattern.get("id"),
        "pattern": pattern,
        "story": story,
        "quality": quality,
        "design_tokens": {
            "corner_radius": tokens.get("corner_radius"),
            "shadow": tokens.get("shadow"),
            "icon_style": tokens.get("icon_style"),
            "illustration_style": tokens.get("illustration_style"),
            "density": tokens.get("density"),
            "typography_safe": typo,
            "style_targets": style_targets,
            "background_styles": tokens.get("background_styles"),
            "accent_styles": tokens.get("accent_styles"),
        },
        "linkedin_image_type": li_type,
        "layout_strategy": layout_strategy,
        "brand_personality": brand_personality,
        "design_style": design_style,
        "thought_leadership_mode": True,
        "style_inspiration": ", ".join(style_targets[:5]),
        "cta_placement": pattern.get("cta_placement") or "bottom_15_percent",
        "top_safe_band": float(typo.get("top_band") or 0.30),
        "bottom_cta_band": float(typo.get("bottom_cta_band") or 0.15),
        "always_avoid": list(pattern.get("always_avoid") or []),
    }


def format_planning_prompt_clause(plan: dict[str, Any]) -> str:
    """Rich clause for the image prompt template."""
    pattern = plan.get("pattern") or {}
    story = plan.get("story") or {}
    tokens = plan.get("design_tokens") or {}
    msg = plan.get("message") or {}
    avoid = plan.get("always_avoid") or []
    inspiration = plan.get("style_inspiration") or "Stripe, Cloudflare, Microsoft Security"

    return (
        f"PATTERN ({plan.get('pattern_id')}): {pattern.get('usage')}. "
        f"VISUAL HIERARCHY: {story.get('visual_hierarchy') or pattern.get('visual_hierarchy')}. "
        f"COMPOSITION FOCUS: {story.get('prompt_focus') or pattern.get('prompt_focus')}. "
        f"{story.get('narrative')} "
        f"Audience: {msg.get('audience')}. Tone: business thought-leadership "
        f"({plan.get('brand_personality')}). "
        f"Style: flat vector, minimal, corporate, premium SaaS, inspired by {inspiration}. "
        f"Design tokens: {tokens.get('corner_radius')} corners, {tokens.get('shadow')} shadows, "
        f"{tokens.get('icon_style')} icons, {tokens.get('density')} density. "
        f"Leave top {int((plan.get('top_safe_band') or 0.3) * 100)}% typography-safe for headline overlay; "
        f"bottom {int((plan.get('bottom_cta_band') or 0.15) * 100)}% for CTA. "
        f"LinkedIn type: {plan.get('linkedin_image_type')} ({plan.get('layout_strategy')}). "
        f"Never: {', '.join(str(a) for a in avoid[:12])}."
    )
