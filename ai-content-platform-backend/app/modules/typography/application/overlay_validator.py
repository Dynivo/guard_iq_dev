"""Overlay validator — overflow, margins, contrast, collisions, logo."""

from __future__ import annotations

from pathlib import Path

from app.modules.typography.application.config_loader import load_typography
from app.modules.typography.domain.models import (
    BrandApplication,
    LayoutEnrichment,
    OverlayValidationResult,
    TypographyAsset,
    TypographyPlan,
)


def _luminance(hex_color: str) -> float:
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return 0.5
    r, g, b = int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255

    def chan(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(a: str, b: str) -> float:
    l1, l2 = _luminance(a), _luminance(b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class DefaultOverlayValidator:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_typography("overlay.yaml", config_dir)

    def validate(
        self,
        asset: TypographyAsset,
        layout: LayoutEnrichment,
        plan: TypographyPlan,
        brand: BrandApplication,
    ) -> OverlayValidationResult:
        reasons: list[str] = []
        min_f = float(self._cfg.get("min_font_size") or 18)
        max_f = float(self._cfg.get("max_font_size") or 96)
        min_c = float(self._cfg.get("min_contrast_ratio") or brand.min_contrast_ratio or 4.5)

        font_ok = True
        overflow_ok = True
        collisions_ok = True
        margins_ok = True
        logo_ok = True
        overflow_hits = 0
        text_layers = [layer for layer in asset.layers if layer.kind == "text"]

        for layer in text_layers:
            size = float(layer.style.get("font_size") or 0)
            if size < min_f or size > max_f:
                font_ok = False
                reasons.append(f"font_size:{layer.role}")
            # Overflow: layer must stay inside canvas
            if layer.x < 0 or layer.y < 0 or layer.x + layer.width > plan.width + 1:
                overflow_ok = False
                overflow_hits += 1
                reasons.append(f"overflow:{layer.role}")
            if layer.y + layer.height > plan.height + 1:
                overflow_ok = False
                overflow_hits += 1
                reasons.append(f"overflow_y:{layer.role}")
            # Margins
            if layer.x / plan.width < layout.margin_left - float(self._cfg.get("margin_tolerance") or 0.01):
                margins_ok = False
                reasons.append(f"margin:{layer.role}")

        # Collision: overlapping text bboxes
        for i, a in enumerate(text_layers):
            for b in text_layers[i + 1 :]:
                if _overlap(a.x, a.y, a.width, a.height, b.x, b.y, b.width, b.height):
                    collisions_ok = False
                    reasons.append(f"collision:{a.role}:{b.role}")

        logo_layers = [layer for layer in asset.layers if layer.role == "logo"]
        if self._cfg.get("require_logo_in_safe_zone", True) and logo_layers:
            logo = logo_layers[0]
            if logo.x < 0 or logo.y < 0:
                logo_ok = False
                reasons.append("logo_placement")

        contrast = _contrast(brand.text_color, brand.primary_color)
        contrast_ok = contrast >= min_c
        if not contrast_ok:
            reasons.append("contrast_low")

        overflow_rate = overflow_hits / max(1, len(text_layers))
        max_overflow = float(self._cfg.get("max_overflow_rate") or 0.05)
        if overflow_rate > max_overflow:
            overflow_ok = False

        typography_score = max(0.0, 1.0 - 0.1 * len(reasons))
        a11y = min(1.0, contrast / max(min_c, 0.1)) if contrast_ok else contrast / min_c * 0.5
        passed = all([overflow_ok, margins_ok, contrast_ok, font_ok, collisions_ok, logo_ok])
        return OverlayValidationResult(
            passed=passed,
            overflow_ok=overflow_ok,
            margins_ok=margins_ok,
            contrast_ok=contrast_ok,
            font_size_ok=font_ok,
            collisions_ok=collisions_ok,
            logo_ok=logo_ok,
            accessibility_score=round(max(0.0, min(1.0, a11y)), 4),
            contrast_score=round(min(1.0, contrast / 21.0), 4),
            typography_score=round(typography_score, 4),
            overflow_rate=round(overflow_rate, 4),
            reason_codes=tuple(dict.fromkeys(reasons)),
        )


def _overlap(x1, y1, w1, h1, x2, y2, w2, h2) -> bool:
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)
