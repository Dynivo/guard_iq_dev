"""Build the Gemini infographic prompt from the draft's own text.

Deliberately minimal: the post's hook and body go in verbatim and the model
decides what to surface. An earlier version fanned the draft out into ~20
structured slots (archetype, layout_type, hierarchy, density, complexity,
coverage_hint, motifs, elements, narrative, metaphor, ...) which pushed the
model toward crowded layouts and, because the body was pre-chopped into a
`subheadline` slot, rendered truncated mid-sentence fragments verbatim.
"""

from __future__ import annotations

import re
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


# Emoji and pictographs render badly (or literally) inside generated images —
# a draft hook ending in a padlock emoji had it drawn into the headline.
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # pictographs, symbols, supplemental
    "\U0001f000-\U0001f2ff"  # tiles, enclosed characters
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicators (flags)
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U00002b00-\U00002bff"  # misc symbols and arrows
    "\U0000200d"  # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text: str) -> str:
    """Remove emoji/pictographs and collapse the whitespace they leave behind."""
    if not text:
        return ""
    cleaned = _EMOJI_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,!?;:])", r"\1", cleaned)
    return cleaned.strip()


def _format_label(fmt: str) -> str:
    if fmt == "linkedin_square":
        return "LinkedIn square"
    return "LinkedIn portrait"


def build_gemini_infographic_prompt(
    spec: VisualDesignSpec,
    *,
    brand: dict[str, Any] | None = None,
    draft: dict[str, Any] | None = None,
    creative_mode: str = "gemini_infographic",
    critic_recommendations: list[str] | None = None,
    logo_as_reference: bool = False,
) -> tuple[str, str]:
    """Return (positive_prompt, negative_prompt) for Gemini text-in-image generation."""
    brand = brand or {}
    draft = draft or {}
    cfg = _cfg()
    mode = (creative_mode or "gemini_infographic").lower()

    # The draft's real text, never pre-truncated into slots. Falls back to the
    # design spec's derived strings only when a draft wasn't supplied.
    hook = strip_emoji(str(draft.get("hook") or spec.headline or "").strip())
    body = strip_emoji(str(draft.get("body") or spec.subheadline or "").strip())

    logo_instruction = (
        "- A logo image is attached: use it for branding. Place it once, small, "
        "in whichever corner suits the finished composition, with clear space "
        "around it. Reproduce it exactly as given — do not redraw, restyle, "
        "recolour or add any wordmark or tagline beside it."
        if logo_as_reference and spec.logo.enabled
        else (
            "- Do not render any logo, wordmark or badge."
            if not spec.logo.enabled
            else "- Do not draw a logo; brand it with colour and type only."
        )
    )

    aspect = str(
        (spec.metadata or {}).get("aspect_ratio")
        or ("1:1" if "square" in spec.format else "4:5")
    )
    ctx = {
        "brand_name": spec.brand_name or brand.get("name") or "Guard IQ",
        "hook": hook or "(no hook supplied)",
        "body": body or "(no body supplied)",
        "format_label": _format_label(spec.format),
        "aspect_ratio": aspect,
        "width": spec.layout.width,
        "height": spec.layout.height,
        "primary_hex": brand.get("primary_color") or spec.brand.primary,
        "secondary_hex": brand.get("secondary_color") or spec.brand.secondary,
        "accent_hex": brand.get("accent_color") or spec.brand.accent,
        "background_hex": spec.brand.background,
        "logo_instruction": logo_instruction,
    }

    sections = [
        str(cfg.get("role") or "").format(**ctx),
        str(cfg.get("post_block") or "").format(**ctx),
        str(cfg.get("image_task") or "").format(**ctx),
        str(cfg.get("brand_block") or "").format(**ctx),
        str(cfg.get("format_block") or "").format(**ctx),
    ]
    if mode in {"gemini_creative", "creative"} and cfg.get("creative_extras"):
        sections.append(str(cfg.get("creative_extras")).strip())

    if critic_recommendations:
        rec_lines = "\n".join(f"  - {r}" for r in critic_recommendations if str(r).strip())
        if rec_lines:
            sections.append(f"FIX ON THIS ATTEMPT:\n{rec_lines}")

    positive = "\n\n".join(s.strip() for s in sections if s and s.strip())
    negative = str(cfg.get("negative") or "misspellings, neon glow, empty poster")
    return positive, negative
