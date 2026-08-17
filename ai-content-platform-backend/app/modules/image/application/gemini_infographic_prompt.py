"""Build Gemini infographic prompts from YAML templates + VisualDesignSpec."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.design_spec import VisualDesignSpec


@lru_cache(maxsize=4)
def _cfg_cached(mtime_ns: int) -> dict[str, Any]:
    del mtime_ns
    return load_yaml("gemini_infographic_prompt.yaml")


def _cfg() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[4]
        / "configs"
        / "image"
        / "gemini_infographic_prompt.yaml"
    )
    mtime = path.stat().st_mtime_ns if path.is_file() else 0
    return _cfg_cached(mtime)


def _join_list(items: Any, *, empty: str = "none") -> str:
    if not items:
        return empty
    vals = [str(x).strip() for x in items if str(x).strip()]
    return "; ".join(vals) if vals else empty


def _format_label(fmt: str) -> str:
    if fmt == "linkedin_square":
        return "LinkedIn square"
    return "LinkedIn portrait"


_LOGO_POSITION_LABELS = {
    "top_left": "top-left corner",
    "top_center": "top-center edge",
    "top_right": "top-right corner",
    "bottom_left": "bottom-left corner",
    "bottom_center": "bottom-center edge",
    "bottom_right": "bottom-right corner",
}


def build_gemini_infographic_prompt(
    spec: VisualDesignSpec,
    *,
    brand: dict[str, Any] | None = None,
    creative_mode: str = "gemini_infographic",
    critic_recommendations: list[str] | None = None,
    logo_as_reference: bool = False,
) -> tuple[str, str]:
    """Return (positive_prompt, negative_prompt) for Gemini text-in-image generation."""
    brand = brand or {}
    cfg = _cfg()
    mode = (creative_mode or "gemini_infographic").lower()

    supporting = _join_list(spec.supporting_stats)
    if spec.statistics:
        supporting_bits = [
            f"{s.value}" + (f" ({s.label})" if s.label and s.label != s.value else "")
            for s in spec.statistics
            if s.role != "hero" and s.value
        ]
        if supporting_bits:
            supporting = "; ".join(supporting_bits)

    facts = spec.factual_constraints or ()
    factual_lines = "\n".join(f"  - {f}" for f in facts) if facts else "  - (use CONTENT strings only)"

    position_label = _LOGO_POSITION_LABELS.get(
        (spec.logo.position or "bottom_right").strip().lower(), "bottom-right corner"
    )
    logo_instruction = (
        f"A logo reference image is attached — place that exact mark once, small "
        f"(roughly 8% of image height), in the {position_label}, with generous clear "
        f"space around it. Nothing else nearby — no extra wordmark, tagline, or text "
        f"beside it beyond what's already in the reference image itself."
        if logo_as_reference and spec.logo.enabled
        else (
            "Do not draw any logo, wordmark, icon, badge, card, or box anywhere — "
            "use the full canvas freely, edge to edge, with no reserved blank area. "
            "A real brand mark with its own backing is composited on top after "
            "generation, in whichever corner suits the finished image best, so it "
            "does not need — and must not have — any space set aside for it."
            if spec.logo.enabled
            else "Do not render any logo mark."
        )
    )

    aspect = str((spec.metadata or {}).get("aspect_ratio") or ("1:1" if "square" in spec.format else "4:5"))
    ctx = {
        "brand_name": spec.brand_name or brand.get("name") or "Guard IQ",
        "category": (spec.category_label or "SECURITY INSIGHT").upper(),
        "headline": (spec.headline or "").strip() or "Security insight",
        "subheadline": (spec.subheadline or "").strip() or "OMIT",
        "primary_stat": (spec.primary_stat or "OMIT").strip(),
        "supporting_stats": supporting,
        "content_blocks": _join_list(spec.content_blocks),
        "cta": (spec.cta or "").strip() or "OMIT",
        "cta_body": (spec.cta_body or "").strip() or "OMIT",
        "source": (spec.source or "").strip() or "OMIT",
        "tagline": (spec.tagline or "").strip() or "OMIT",
        "factual_constraints": factual_lines,
        "narrative": (spec.story.narrative or "").strip() or "OMIT",
        "metaphor": (spec.story.metaphor or "").strip() or "OMIT",
        "viewer_takeaway": (spec.story.viewer_takeaway or "").strip() or "OMIT",
        "format_label": _format_label(spec.format),
        "aspect_ratio": aspect,
        "width": spec.layout.width,
        "height": spec.layout.height,
        "archetype": spec.design_archetype,
        "layout_type": spec.layout.type,
        "primary_focus": spec.hierarchy.primary_focus,
        "secondary_focus": spec.hierarchy.secondary_focus,
        "density": spec.hierarchy.density or spec.layout.density,
        "complexity": spec.hierarchy.complexity,
        "coverage_hint": spec.hierarchy.coverage_hint,
        "brand_variant": spec.brand_variant,
        "visual_motifs": _join_list(spec.visual_motifs),
        "visual_elements": _join_list(spec.visual_elements),
        "visual_concept": (spec.visual_concept or "").strip() or "OMIT",
        "primary_hex": brand.get("primary_color") or spec.brand.primary,
        "secondary_hex": brand.get("secondary_color") or spec.brand.secondary,
        "accent_hex": brand.get("accent_color") or spec.brand.accent,
        "background_hex": spec.brand.background,
        "text_hex": spec.brand.text,
        "logo_instruction": logo_instruction,
        "image_generation_instruction": (
            spec.image_generation_instruction or "Create a professional LinkedIn infographic."
        ),
    }

    sections = [
        str(cfg.get("instruction_prefix") or "{image_generation_instruction}").format(**ctx),
        str(cfg.get("role") or "").format(**ctx),
        str(cfg.get("content_block") or "").format(**ctx),
        str(cfg.get("factual_block") or "").format(**ctx),
        str(cfg.get("story_block") or "").format(**ctx),
        str(cfg.get("layout_block") or "").format(**ctx),
        str(cfg.get("design_language_block") or "").format(**ctx),
        str(cfg.get("brand_block") or "").format(**ctx),
        str(cfg.get("text_rules_block") or "").format(**ctx),
    ]
    if mode in {"gemini_creative", "creative"}:
        sections.append(str(cfg.get("creative_extras") or "").strip())

    if critic_recommendations:
        rec_lines = "\n".join(f"  - {r}" for r in critic_recommendations if str(r).strip())
        if rec_lines:
            sections.append(f"QUALITY RETRY GUIDANCE (must address):\n{rec_lines}")

    if spec.relationships:
        rel_lines = "\n".join(
            f"  - {r.from_node} → {r.to_node}"
            + (f" ({r.label})" if r.label else "")
            for r in spec.relationships
        )
        sections.append(f"RELATIONSHIPS TO VISUALIZE:\n{rel_lines}")

    positive = "\n\n".join(s.strip() for s in sections if s and s.strip())
    negative = str(cfg.get("negative") or "misspellings, neon glow, empty poster")
    return positive, negative
