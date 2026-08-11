"""Brand Engine — BrandKit + DesignTokens → BrandApplication."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.typography.application.config_loader import load_brand
from app.modules.typography.application.design_tokens import DesignTokenEngine
from app.modules.typography.domain.models import BrandApplication


class DefaultBrandEngine:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._tokens = load_brand("tokens.yaml", config_dir)
        self._registry = load_brand("registry.yaml", config_dir)
        self._design = DesignTokenEngine(config_dir)

    def apply(
        self,
        brand_kit: dict[str, Any],
        *,
        variant: str = "dark",
    ) -> BrandApplication:
        design = self._design.resolve(variant=variant, brand_kit=brand_kit)
        colors = design.colors
        typography = design.typography
        families = dict(typography.get("families") or {})

        primary = str(brand_kit.get("primary_color") or colors.get("surface") or "#0A1F2B")
        accent = str(brand_kit.get("accent_color") or colors.get("accent") or "#1A5CB0")
        secondary = str(brand_kit.get("secondary_color") or "#FFFFFF")
        text_primary = str(colors.get("text_primary") or "#FFFFFF")

        return BrandApplication(
            brand_id=str(brand_kit.get("id") or brand_kit.get("brand_id") or "default"),
            brand_name=str(brand_kit.get("name") or "Brand"),
            primary_color=primary,
            secondary_color=secondary,
            accent_color=accent,
            text_color=text_primary,
            font_heading=str(
                brand_kit.get("font_heading") or families.get("heading") or "Inter"
            ),
            font_body=str(brand_kit.get("font_body") or families.get("body") or "Inter"),
            logo_object_key=brand_kit.get("logo_object_key"),
            footer_text=str(brand_kit.get("footer_text") or ""),
            services_line=str(brand_kit.get("services_line") or ""),
            variant=variant,
            min_contrast_ratio=float(
                colors.get("min_contrast_ratio")
                or self._tokens.get("defaults", {}).get("min_contrast_ratio")
                or 4.5
            ),
            tokens=dict(colors),
            design_tokens=design,
            metadata={
                "registry": list(self._registry.get("brands") or []),
                "allowed_fonts": list(design.metadata.get("allowed_fonts") or []),
                "source": "brand_engine",
            },
        )
