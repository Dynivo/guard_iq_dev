"""Asset intelligence — colors, whitespace, OCR candidate regions (no OCR engine)."""

from __future__ import annotations

import io
from collections import Counter
from typing import Any

from PIL import Image

from app.modules.image.domain.models import (
    AssetIntelligenceReport,
    EnrichedVisualBrief,
    LayoutPlan,
    ScenePlan,
)


def _hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


class DefaultAssetAnalyzer:
    def analyze(
        self,
        image_bytes: bytes,
        *,
        scene: ScenePlan,
        brief: EnrichedVisualBrief,
        layout: LayoutPlan | None = None,
        brand: dict[str, Any] | None = None,
    ) -> AssetIntelligenceReport:
        brand = brand or {}
        dominant: list[str] = []
        whitespace: list[dict[str, Any]] = []
        ocr_regions: list[dict[str, Any]] = []
        safe_crop: list[dict[str, Any]] = []

        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = img.size
            # Quantize for dominant colors
            small = img.resize((64, 64))
            colors = list(small.get_flattened_data())
            counted = Counter((r // 32 * 32, g // 32 * 32, b // 32 * 32) for r, g, b in colors)
            for (r, g, b), _ in counted.most_common(5):
                dominant.append(_hex(r, g, b))

            gray = img.convert("L")
            # Row brightness → whitespace bands
            row_means = []
            step = max(1, h // 40)
            for y in range(0, h, step):
                band = gray.crop((0, y, w, min(h, y + step)))
                pixels = list(band.get_flattened_data())
                row_means.append((y / h, sum(pixels) / max(1, len(pixels))))
            for y_norm, mean in row_means:
                if mean > 200 or mean < 25:
                    whitespace.append(
                        {
                            "role": "bright_band" if mean > 200 else "dark_band",
                            "y": round(y_norm, 4),
                            "mean_luma": round(mean, 2),
                        }
                    )

            # OCR candidate regions = layout text regions (geometry only; no OCR)
            if layout:
                for role, region in (
                    ("title", layout.title),
                    ("subtitle", layout.subtitle),
                    ("cta", layout.cta),
                    ("footer", layout.footer),
                ):
                    if region:
                        ocr_regions.append({**region.to_dict(), "candidate_for": role})
                if layout.illustration_safe:
                    safe_crop.append(layout.illustration_safe.to_dict())
            else:
                ocr_regions.append(
                    {"role": "bottom_band", "x": 0.08, "y": 0.7, "width": 0.84, "height": 0.22}
                )
                safe_crop.append(
                    {"role": "center", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.55}
                )
        except Exception:
            dominant = list(brief.color_palette[:5])

        objects = tuple(
            list(scene.objects) + list(scene.icons) + list(scene.foreground)
        )[:12]
        brand_palette = tuple(
            c
            for c in (
                brand.get("primary_color"),
                brand.get("accent_color"),
                *list(brief.color_palette),
            )
            if c
        )

        return AssetIntelligenceReport(
            dominant_colors=tuple(dominant),
            objects=objects,
            whitespace=tuple(whitespace[:20]),
            ocr_regions=tuple(ocr_regions),
            safe_crop_areas=tuple(safe_crop),
            brand_palette=brand_palette,
            metadata={"analyzer": "deterministic_pillow", "no_ocr_engine": True},
        )
