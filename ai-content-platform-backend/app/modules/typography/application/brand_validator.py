"""Brand validator — colors, fonts, spacing, compliance."""

from __future__ import annotations

from pathlib import Path

from app.modules.typography.application.config_loader import load_brand
from app.modules.typography.domain.models import (
    BrandApplication,
    BrandValidationResult,
    TypographyAsset,
    TypographyPlan,
)


class DefaultBrandValidator:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._tokens = load_brand("tokens.yaml", config_dir)

    def validate(
        self,
        brand: BrandApplication,
        asset: TypographyAsset,
        plan: TypographyPlan,
    ) -> BrandValidationResult:
        reasons: list[str] = []
        allowed = set(self._tokens.get("allowed_fonts") or [])
        colors_ok = all(
            str(c).startswith("#") and len(str(c)) in (4, 7)
            for c in (brand.primary_color, brand.accent_color, brand.text_color)
        )
        if not colors_ok:
            reasons.append("invalid_brand_hex")

        fonts_ok = True
        if allowed:
            if brand.font_heading not in allowed or brand.font_body not in allowed:
                fonts_ok = False
                reasons.append("font_not_allowed")

        spacing_ok = plan.spacing_scale > 0
        if not spacing_ok:
            reasons.append("bad_spacing_scale")

        alignment_ok = all(
            s.alignment in ("left", "center", "right") for s in plan.styles
        )
        if not alignment_ok:
            reasons.append("bad_alignment")

        compliance_ok = bool(brand.brand_name) and colors_ok
        if not brand.brand_name:
            reasons.append("missing_brand_name")

        # Text layers should use brand fonts from plan
        for layer in asset.layers:
            if layer.kind != "text":
                continue
            family = str(layer.style.get("font_family") or "")
            if allowed and family and family not in allowed:
                fonts_ok = False
                reasons.append(f"layer_font:{layer.role}")

        score = max(0.0, 1.0 - 0.12 * len(reasons))
        passed = colors_ok and fonts_ok and spacing_ok and alignment_ok and compliance_ok
        return BrandValidationResult(
            passed=passed,
            colors_ok=colors_ok,
            fonts_ok=fonts_ok,
            spacing_ok=spacing_ok,
            alignment_ok=alignment_ok,
            compliance_ok=compliance_ok,
            brand_score=round(score, 4),
            reason_codes=tuple(dict.fromkeys(reasons)),
            metadata={"brand_id": brand.brand_id},
        )
