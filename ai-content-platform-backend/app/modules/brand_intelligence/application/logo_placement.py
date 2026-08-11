"""Detect preferred logo corner from brand creatives + resolve typography defaults."""

from __future__ import annotations

import io
from collections import Counter
from typing import Any

# Corner keys match LogoPlacementOptions.position
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


def majority_logo_position(samples: list[dict[str, Any]]) -> str | None:
    """Pick the most common detected logo corner from vision analyses."""
    votes: list[str] = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        if not s.get("logo_presence"):
            continue
        pos = str(s.get("logo_position") or "").strip().lower()
        if pos in CORNERS or pos == "center":
            votes.append(pos)
    if not votes:
        return None
    return Counter(votes).most_common(1)[0][0]


def detect_logo_corner_from_bytes(raw: bytes) -> dict[str, Any]:
    """Heuristic corner logo detection via PIL (no ML vendor lock-in).

    Scores each corner patch for “badge-like” contrast / edge energy vs image center.
    Returns logo_presence + logo_position when confidence is enough.
    """
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError:
        return {
            "logo_presence": False,
            "logo_position": None,
            "logo_confidence": 0.0,
            "engine": "heuristic_no_pillow",
        }

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return {
            "logo_presence": False,
            "logo_position": None,
            "logo_confidence": 0.0,
            "engine": "heuristic_unreadable",
        }

    w, h = img.size
    if w < 64 or h < 64:
        return {
            "logo_presence": False,
            "logo_position": None,
            "logo_confidence": 0.0,
            "engine": "heuristic_too_small",
        }

    side = max(24, int(min(w, h) * 0.18))
    gray = img.convert("L").filter(ImageFilter.FIND_EDGES)
    cx0, cy0 = w // 2 - side // 2, h // 2 - side // 2
    center = gray.crop((cx0, cy0, cx0 + side, cy0 + side))
    center_energy = float(ImageStat.Stat(center).mean[0])

    boxes = {
        "top_left": (0, 0, side, side),
        "top_right": (w - side, 0, w, side),
        "bottom_left": (0, h - side, side, h),
        "bottom_right": (w - side, h - side, w, h),
    }
    scores: dict[str, float] = {}
    for name, box in boxes.items():
        patch = gray.crop(box)
        energy = float(ImageStat.Stat(patch).mean[0])
        # Prefer corners that are busier than the center (logo badge / wordmark edges)
        scores[name] = energy - center_energy * 0.35

        # Alpha badge boost: non-opaque or high color variance in RGBA corner
        rgba = img.crop(box)
        alphas = rgba.split()[3]
        a_mean = float(ImageStat.Stat(alphas).mean[0])
        if 20 < a_mean < 250:
            scores[name] += 12.0
        colors = rgba.convert("RGB")
        extrema = colors.getextrema()
        spread = sum(float(hi - lo) for lo, hi in extrema) / 3.0
        if spread > 40:
            scores[name] += min(20.0, spread / 8.0)

    best_pos, best_score = max(scores.items(), key=lambda kv: kv[1])
    ordered = sorted(scores.values(), reverse=True)
    gap = ordered[0] - ordered[1] if len(ordered) > 1 else ordered[0]
    confidence = max(0.0, min(1.0, (best_score / 40.0) * 0.55 + (gap / 25.0) * 0.45))
    present = confidence >= 0.35 and best_score > 8.0
    return {
        "logo_presence": present,
        "logo_position": best_pos if present else None,
        "logo_confidence": round(confidence, 3),
        "corner_scores": {k: round(v, 2) for k, v in scores.items()},
        "engine": "heuristic_corner",
    }


def resolve_logo_placement_defaults(
    visual_dna: dict[str, Any] | None,
    *,
    has_logo_asset: bool,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build typography logo options: optional include + brand-learned or user override."""
    dna = visual_dna or {}
    learned = str(dna.get("preferred_logo_position") or dna.get("logo_position") or "").strip().lower()
    if learned not in CORNERS and learned != "center":
        learned = "bottom_right"  # common LinkedIn creative default

    base = {
        "include_logo": False,  # optional by default — user opts in
        "position": learned,
        "position_source": "brand_learned" if dna.get("preferred_logo_position") else "default",
        "custom_x": None,
        "custom_y": None,
        "size": "m",
        "opacity": 1.0,
        "margin": 0.04,
        "safe_area": True,
        "has_logo_asset": has_logo_asset,
        "learned_position": learned if dna.get("preferred_logo_position") else None,
    }
    if not override:
        return base

    if "include_logo" in override:
        base["include_logo"] = bool(override["include_logo"]) and has_logo_asset
    pos = override.get("position")
    if pos == "brand_default" or pos == "learned":
        base["position"] = learned
        base["position_source"] = "brand_learned"
    elif isinstance(pos, str) and pos:
        base["position"] = pos
        base["position_source"] = "user"
    for key in ("custom_x", "custom_y", "size", "opacity", "margin", "safe_area"):
        if key in override and override[key] is not None:
            base[key] = override[key]
    return base
