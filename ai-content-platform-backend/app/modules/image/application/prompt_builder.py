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
        text_in_image = bool(meta.get("text_in_image", True))
        palette_colours = resolve_brand_palette(brand, brief.color_palette)
        palette_clause = format_palette_clause(palette_colours)

        brand_name = str(brand.get("name") or "the brand").strip() or "the brand"
        primary_color = palette_colours[0] if palette_colours else "#0A1F2B"
        accent_color = str(
            brand.get("accent_color") or (palette_colours[2] if len(palette_colours) > 2 else "#1A5CB0")
        )
        brand_personality = str(
            brand.get("personality")
            or brand.get("voice")
            or brand.get("tone")
            or "UK IT & cybersecurity managed services provider"
        )
        logo_on_dark = str(
            self._cfg.get("logo_description_on_dark") or "a simple brand mark icon"
        )
        logo_on_light = str(
            self._cfg.get("logo_description_on_light") or "a simple brand mark icon"
        )
        surface_color = str(self._cfg.get("surface_color") or "#F4F7F5")

        # Real post copy for each card slot — never abstracted into 2-4 word labels.
        # No CTA/callout slot here on purpose — the client asked for calls-to-action
        # to never render on the image itself.
        headline = str(meta.get("headline") or content_subject).strip()
        subtext = str(meta.get("subtext") or "").strip()
        eyebrow = str(meta.get("eyebrow") or "INSIGHT").strip()
        stat_number = str(meta.get("stat_number") or "NEW").strip()
        stat_caption = str(meta.get("stat_caption") or headline).strip()
        short_labels = (
            str(
                meta.get("education_labels")
                or meta.get("short_labels")
                or meta.get("body_key_ideas")
                or ""
            ).strip()
            or "Key insight; Stay secure; Act early"
        )
        labels = [
            " ".join(item.strip().split()[:4])
            for item in short_labels.split(";")
            if item.strip()
        ]
        for fallback in ("Key issue", "What it exposes", "Why it matters"):
            if len(labels) >= 3:
                break
            if fallback.lower() not in {label.lower() for label in labels}:
                labels.append(fallback)
        short_labels = "; ".join(labels[:3])
        education_blob = f"{eyebrow} {headline} {subtext}".lower()
        education_heading = (
            "THE RISK CHAIN"
            if any(
                term in education_blob
                for term in (
                    "alert",
                    "risk",
                    "breach",
                    "threat",
                    "exposed",
                    "vulnerab",
                    "attack",
                    "malware",
                    "ransomware",
                    "phishing",
                )
            )
            else "KEY TAKEAWAYS"
        )
        # Free-text guidance from the "Options" tip field on the draft page — e.g.
        # a client asking to change something about an already-generated image.
        image_guidance = str(meta.get("image_guidance") or "").strip()

        # Each variant of a draft cycles through style_order — same provider, different
        # template — instead of the old "one provider per variant" comparison approach.
        style_order = [str(s) for s in (self._cfg.get("style_order") or ["alert_card"])]
        style_key = style_order[variant_index % len(style_order)]
        templates = self._cfg.get("templates") or {}
        template = str(templates.get(style_key) or self._cfg.get("template") or "{headline}")

        variant_note = ""
        if variant_index >= len(style_order):
            variant_note = (
                " Use a subtly different layout balance from the primary variant "
                "while keeping the same structure."
            )

        positive = template.format(
            brand_name=brand_name,
            brand_name_upper=brand_name.upper(),
            brand_personality=brand_personality,
            primary_color=primary_color,
            accent_color=accent_color,
            surface_color=surface_color,
            logo_description_on_dark=logo_on_dark,
            logo_description_on_light=logo_on_light,
            eyebrow=eyebrow,
            headline=headline,
            subtext=subtext,
            stat_number=stat_number,
            stat_caption=stat_caption,
            short_labels=short_labels,
            education_heading=education_heading,
            variant_note=variant_note,
        )
        if image_guidance:
            positive = (
                f"{positive.strip()} ADDITIONAL INSTRUCTION FROM THE USER — follow this "
                f"precisely; it takes priority over anything above it if there's a conflict: "
                f"{image_guidance}"
            )
        negative = brief.negative_prompt or str(
            self._cfg.get("default_negative")
            or "blurry text, misspelled words, watermark, cluttered layout"
        )
        # Fold negatives into positive for providers (OpenAI Images) that ignore negative_prompt
        avoid_prefix = str(self._cfg.get("avoid_prefix") or "Strictly avoid")
        if negative.strip() and avoid_prefix.lower() not in positive.lower():
            positive = f"{positive.strip()}. {avoid_prefix}: {negative.strip()}"

        wf = workflow_id or str(self._cfg.get("default_workflow_id") or "flux_dev")
        seed_src = f"{positive.strip()}|{negative}|{wf}|v{variant_index}|{style_key}"
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
                "template_style": style_key,
                # Intended on-image text — used by the post-generation text-accuracy
                # check (engine.py) to catch rendered typos like "exposoed", not to
                # build the prompt (that already happened above).
                "card_copy": {
                    "brand_name": brand_name,
                    "eyebrow": eyebrow,
                    "headline": headline,
                    "subtext": subtext,
                    "education_heading": education_heading,
                    "education_labels": short_labels,
                    "stat_number": stat_number,
                    "stat_caption": stat_caption,
                },
            },
            metadata={
                "audience": brief.audience,
                "visual_tone": brief.visual_tone,
                "content_subject": content_subject,
                "brand_palette": palette_colours,
                "text_in_image": text_in_image,
                "never_calls_providers": True,
                "variant_index": variant_index,
                "template_style": style_key,
                "visual_pattern_id": meta.get("visual_pattern_id"),
                "post_intent": meta.get("post_intent"),
                "visual_quality_score": meta.get("visual_quality_score"),
            },
        )
