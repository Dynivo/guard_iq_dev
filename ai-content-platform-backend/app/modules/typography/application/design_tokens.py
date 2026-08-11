"""Design Token Engine — merge BrandKit + token YAML into DesignTokens."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.typography.application.config_loader import load_brand
from app.modules.typography.domain.models import DesignTokens


class DesignTokenEngine:
    """Builds structured design token groups without hardcoding in the renderer."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._raw = load_brand("tokens.yaml", config_dir)

    def resolve(
        self,
        *,
        variant: str = "dark",
        brand_kit: dict[str, Any] | None = None,
    ) -> DesignTokens:
        brand_kit = brand_kit or {}
        defaults = dict(self._raw.get("defaults") or {})
        variants = self._raw.get("variants") or {}
        variant_colors = dict(variants.get(variant) or variants.get("dark") or {})
        colors = {**defaults, **variant_colors}
        if brand_kit.get("primary_color"):
            colors["surface"] = brand_kit["primary_color"]
        if brand_kit.get("accent_color"):
            colors["accent"] = brand_kit["accent_color"]

        typography = dict(self._raw.get("typography") or {})
        if brand_kit.get("font_heading"):
            typography = {
                **typography,
                "families": {
                    **dict(typography.get("families") or {}),
                    "heading": brand_kit["font_heading"],
                    "body": brand_kit.get("font_body") or brand_kit["font_heading"],
                },
            }

        return DesignTokens(
            typography=typography,
            spacing=dict(self._raw.get("spacing") or {}),
            radius=dict(self._raw.get("radius") or {}),
            elevation=dict(self._raw.get("elevation") or {}),
            shadows=dict(self._raw.get("shadows") or {}),
            borders=dict(self._raw.get("borders") or {}),
            opacity=dict(self._raw.get("opacity") or {}),
            animation=dict(self._raw.get("animation") or {}),
            colors=colors,
            metadata={
                "variant": variant,
                "allowed_fonts": list(self._raw.get("allowed_fonts") or []),
                "source": "design_token_engine",
            },
        )
