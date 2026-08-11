"""Image prompt builder — outputs ImagePromptRequest only.

Brand Kit colours are injected into the positive prompt. Short 2–4 word labels are
encouraged for educational infographics; paragraphs remain banned. Negatives are
also folded into the positive string so providers without a native negative channel
(OpenAI Images) still comply.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    ImagePromptRequest,
    ScenePlan,
)

# Fallback only when Brand Kit is missing — still professional, not muddy brown.
_FALLBACK_PALETTE = ("#0A1F2B", "#1A5CB0", "#0D7377", "#F4F7F5")


def resolve_brand_palette(
    brand: dict[str, Any] | None,
    brief_palette: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    """Prefer Brand Kit hexes; fall back to brief palette, then house defaults."""
    brand = brand or {}
    colours: list[str] = []
    for key in ("primary_color", "secondary_color", "accent_color"):
        raw = str(brand.get(key) or "").strip()
        if raw.startswith("#") and len(raw) >= 4 and raw.upper() not in {c.upper() for c in colours}:
            colours.append(raw.upper() if len(raw) == 7 else raw)
    # Soft neutrals from brief that aren't already present
    for c in brief_palette or ():
        s = str(c).strip()
        if s.startswith("#") and s.upper() not in {x.upper() for x in colours}:
            colours.append(s)
    if not colours:
        colours = list(_FALLBACK_PALETTE)
    # Ensure we always have a light surface for clean backgrounds
    if not any(c.upper() in {"#FFFFFF", "#F4F7F5", "#F8FAFC", "#EEF2F6"} for c in colours):
        colours.append("#F4F7F5")
    return colours[:6]


def format_palette_clause(colours: list[str]) -> str:
    if not colours:
        return "primary brand navy, accent blue, clean off-white"
    named = ", ".join(colours)
    return (
        f"{named} — use primary as dominant field, accent for focal highlights, "
        f"light surface for clean negative space; do not invent muddy browns or off-brand neons"
    )


class DefaultImagePromptBuilder:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("prompt_builder.yaml", config_dir)

    def build(
        self,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        *,
        brand: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        variant_index: int = 0,
        seed_override: int | None = None,
    ) -> ImagePromptRequest:
        brand = brand or {}
        meta = brief.metadata or {}
        content_subject = str(
            meta.get("content_subject") or brief.focal_point or "LinkedIn educational post"
        )
        must_depict = str(
            meta.get("must_depict")
            or brief.scene_hint
            or "flat branded illustration matching the post topic"
        )
        visual_elements = str(
            meta.get("visual_elements")
            or "one clear focal subject with relevant educational graphic accents, no text"
        )
        # Abstract icon themes only — never raw post sentences (those caused wrong scenes + misspellings)
        body_key_ideas = str(
            meta.get("short_labels")
            or meta.get("body_key_ideas")
            or meta.get("icon_themes")
            or ""
        )
        charts = ", ".join(scene.charts) or str(meta.get("charts") or "none")
        graphs = ", ".join(scene.graphs) or str(meta.get("graphs") or "none")
        objects = ", ".join(scene.objects) or (
            ", ".join(brief.infographic_suggestions[:4]) if brief.infographic_suggestions else "none"
        )
        text_in_image = bool(meta.get("text_in_image", True))
        palette_colours = resolve_brand_palette(brand, brief.color_palette)
        palette_clause = format_palette_clause(palette_colours)
        brand_direction = (
            brief.brand_direction
            or f"{brand.get('name') or 'Brand'} — palette {', '.join(palette_colours[:3])}"
        )
        planning_clause = str(
            meta.get("planning_clause")
            or meta.get("visual_story")
            or "Premium SaaS editorial infographic with clear visual hierarchy."
        )
        visual_story = str(meta.get("visual_story") or planning_clause)
        visual_hierarchy = str(
            meta.get("visual_hierarchy")
            or (meta.get("visual_plan") or {}).get("story", {}).get("visual_hierarchy")
            or "headline band → diagram → outcome"
        )
        style_inspiration = str(
            meta.get("style_inspiration")
            or "CrowdStrike, Microsoft Security, Cloudflare, Stripe, Linear, Vanta"
        )

        template = str(
            self._cfg.get("template")
            or "{style} illustration, {scene}, {intent}, about {content_subject}, colours {palette}"
        )
        variant_note = ""
        if variant_index > 0:
            variant_note = f", alternate composition variant {variant_index + 1}"
        positive = template.format(
            style=brief.illustration_style or self._cfg.get("style_prefix") or "professional",
            theme=brief.theme,
            scene=(brief.scene_hint or scene.layout) + variant_note,
            foreground=", ".join(scene.foreground) or "subject",
            background=", ".join(scene.background) or "clean light brand-surface backdrop",
            icons=", ".join(scene.icons) or "subtle icons",
            composition=composition.balance,
            camera=composition.camera,
            focus=composition.focus,
            intent=brief.image_intent or brief.purpose,
            brand_direction=brand_direction,
            content_subject=content_subject,
            must_depict=must_depict,
            visual_elements=visual_elements,
            body_key_ideas=body_key_ideas or "Hidden risk; Detect; Resolve; Compliance",
            charts=charts,
            graphs=graphs,
            objects=objects,
            palette=palette_clause,
            planning_clause=planning_clause,
            visual_story=visual_story,
            visual_hierarchy=visual_hierarchy,
            style_inspiration=style_inspiration,
        )
        negative = brief.negative_prompt or str(
            self._cfg.get("default_negative")
            or "paragraphs, tiny illegible text, misspelled text, neon glow, black void, watermark"
        )
        # Fold negatives into positive for providers (OpenAI Images) that ignore negative_prompt
        avoid_prefix = str(self._cfg.get("avoid_prefix") or "Strictly avoid")
        if negative.strip() and avoid_prefix.lower() not in positive.lower():
            positive = f"{positive.strip()}. {avoid_prefix}: {negative.strip()}"

        wf = workflow_id or str(self._cfg.get("default_workflow_id") or "flux_dev")
        seed_src = f"{positive.strip()}|{negative}|{wf}|v{variant_index}"
        seed = (
            int(seed_override)
            if seed_override is not None
            else abs(hash(seed_src)) % (2**31)
        )
        return ImagePromptRequest(
            positive_prompt=positive.strip(),
            negative_prompt=negative,
            width=composition.width,
            height=composition.height,
            style=brief.illustration_style or "professional",
            workflow_id=wf,
            workflow_version=str(self._cfg.get("default_workflow_version") or "1"),
            seed=seed,
            parameters={
                "typography_safe_area": brief.typography_safe_area,
                "palette": palette_colours,
                "variant_index": variant_index,
                "content_subject": content_subject,
            },
            metadata={
                "audience": brief.audience,
                "visual_tone": brief.visual_tone,
                "content_subject": content_subject,
                "brand_palette": palette_colours,
                "text_in_image": text_in_image,
                "never_calls_providers": True,
                "variant_index": variant_index,
                "visual_pattern_id": meta.get("visual_pattern_id"),
                "post_intent": meta.get("post_intent"),
                "visual_quality_score": meta.get("visual_quality_score"),
            },
        )
