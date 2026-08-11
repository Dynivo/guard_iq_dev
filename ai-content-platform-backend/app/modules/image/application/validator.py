"""Post-generation image validation with VisualQualityBreakdown."""

from __future__ import annotations

import io
import statistics
from pathlib import Path
from typing import Any

from PIL import Image

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    ImageValidationResult,
    VisualQualityBreakdown,
)


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    s = (value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return None
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return None


def _brand_rgb_targets(brief: EnrichedVisualBrief, brand: dict[str, Any]) -> list[tuple[int, int, int]]:
    colours: list[str] = []
    for key in ("primary_color", "secondary_color", "accent_color"):
        raw = str(brand.get(key) or "")
        if raw.startswith("#"):
            colours.append(raw)
    for c in brief.color_palette or ():
        s = str(c)
        if s.startswith("#"):
            colours.append(s)
    out: list[tuple[int, int, int]] = []
    for c in colours:
        rgb = _hex_to_rgb(c)
        if rgb and rgb not in out:
            out.append(rgb)
    return out


def _near_any_brand(
    pixel: tuple[int, ...],
    targets: list[tuple[int, int, int]],
    *,
    max_dist: float = 95.0,
) -> bool:
    r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
    for tr, tg, tb in targets:
        dist = ((r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2) ** 0.5
        if dist <= max_dist:
            return True
    return False


class DefaultImageValidator:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("validation.yaml", config_dir)

    def validate(
        self,
        image_bytes: bytes,
        *,
        composition: CompositionPlan,
        brief: EnrichedVisualBrief,
        brand: dict[str, Any] | None = None,
    ) -> ImageValidationResult:
        reasons: list[str] = []
        brand = brand or {}
        integrity = True
        contrast_score = 0.5
        aesthetic = 0.7
        whitespace_score = 0.7
        composition_score = 0.75
        artifact_score = 1.0
        brand_score = 0.7

        if self._cfg.get("require_png_magic", True):
            integrity = image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
            if not integrity:
                reasons.append("bad_png_magic")

        resolution_ok = True
        aspect_ok = True
        blur_ok = True
        artifacts_ok = True
        palette_ok = True
        try:
            img = Image.open(io.BytesIO(image_bytes))
            w, h = img.size
            min_w = int(self._cfg.get("min_width") or 512)
            min_h = int(self._cfg.get("min_height") or 512)
            resolution_ok = w >= min_w and h >= min_h
            if not resolution_ok:
                reasons.append("resolution_too_small")
                composition_score -= 0.2
            expected = composition.width / max(1, composition.height)
            actual = w / max(1, h)
            tol = float(self._cfg.get("expected_aspect_tolerance") or 0.08)
            aspect_ok = abs(expected - actual) <= tol
            if not aspect_ok:
                reasons.append("aspect_mismatch")
                composition_score -= 0.25
            else:
                composition_score = min(1.0, composition_score + 0.15)

            gray = img.convert("L")
            data = list(gray.getdata())
            sample = data[:: max(1, len(data) // 2000)]
            if len(sample) > 2:
                var = statistics.pvariance(sample)
                blur_ok = var >= float(self._cfg.get("blur_variance_threshold") or 10.0)
                if not blur_ok:
                    reasons.append("possible_blur")
                    aesthetic -= 0.3
                contrast_score = min(1.0, max(0.0, var / 2500.0))
                # Whitespace: mid-luma band share
                mid = sum(1 for p in sample if 40 < p < 220)
                whitespace_score = min(1.0, mid / max(1, len(sample)))

            extreme = sum(1 for p in sample if p < 5 or p > 250)
            if sample and extreme / len(sample) > 0.92:
                artifacts_ok = False
                artifact_score = 0.2
                reasons.append("flat_artifact")
            else:
                artifact_score = max(0.4, 1.0 - (extreme / max(1, len(sample))))

            if brief.color_palette or brand.get("primary_color"):
                rgb = img.convert("RGB")
                step = max(
                    1, (rgb.width * rgb.height) // int(self._cfg.get("palette_sample_pixels") or 64)
                )
                pixels = list(rgb.getdata())[::step]
                targets = _brand_rgb_targets(brief, brand)
                if pixels and targets:
                    near = sum(1 for px in pixels if _near_any_brand(px, targets))
                    ratio = near / max(1, len(pixels))
                    min_ratio = float(self._cfg.get("min_brand_pixel_ratio") or 0.08)
                    palette_ok = ratio >= min_ratio
                    brand_score = min(1.0, ratio / max(min_ratio, 0.01))
                    if not palette_ok:
                        reasons.append("palette_mismatch")
                        brand_score = min(brand_score, 0.35)
                else:
                    # Legacy fallback: prefer cooler brand-like tones over muddy browns
                    cool = sum(1 for r, g, b in pixels if b >= r - 10 and (b + g) > r + 20)
                    muddy = sum(
                        1
                        for r, g, b in pixels
                        if r > 80 and g > 60 and b < 70 and abs(r - g) < 40
                    )
                    palette_ok = cool >= muddy or not brief.color_palette
                    brand_score = min(1.0, cool / max(1, len(pixels) * 0.12)) if pixels else 0.5
                    if muddy > cool and pixels:
                        reasons.append("muddy_palette")
                        brand_score = min(brand_score, 0.4)
                        palette_ok = False
        except Exception:
            integrity = False
            reasons.append("decode_failed")
            composition_score = 0.0
            contrast_score = 0.0
            aesthetic = 0.0

        safe_ok = bool(brief.typography_safe_area)
        typography_safety = 1.0 if safe_ok else 0.2
        if not safe_ok:
            reasons.append("missing_safe_area_meta")

        breakdown = VisualQualityBreakdown(
            composition=round(max(0.0, min(1.0, composition_score)), 4),
            contrast=round(max(0.0, min(1.0, contrast_score)), 4),
            brand_alignment=round(max(0.0, min(1.0, brand_score)), 4),
            whitespace=round(max(0.0, min(1.0, whitespace_score)), 4),
            typography_safety=round(typography_safety, 4),
            aesthetic=round(max(0.0, min(1.0, aesthetic)), 4),
            artifact=round(max(0.0, min(1.0, artifact_score)), 4),
        )
        score = breakdown.composite()
        min_q = float(self._cfg.get("min_quality_score") or 0.55)
        aspect_hard = bool(self._cfg.get("aspect_mismatch_is_hard_fail", True))
        passed = (
            integrity
            and resolution_ok
            and (aspect_ok or not aspect_hard)
            and blur_ok
            and artifacts_ok
            and safe_ok
            and score >= min_q
        )
        return ImageValidationResult(
            passed=passed,
            score=score,
            resolution_ok=resolution_ok,
            aspect_ratio_ok=aspect_ok,
            brand_palette_ok=palette_ok,
            blur_ok=blur_ok,
            artifacts_ok=artifacts_ok,
            typography_safe_area_ok=safe_ok,
            file_integrity_ok=integrity,
            reason_codes=tuple(reasons),
            breakdown=breakdown,
            metadata={"brand": brand.get("name")},
        )
