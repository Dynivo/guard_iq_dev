"""Typography planner — sizes, weights, spacing, hierarchy; honors template_id."""

from __future__ import annotations

from pathlib import Path

from app.modules.typography.application.config_loader import load_typography
from app.modules.typography.application.templates import LayoutTemplateRegistry
from app.modules.typography.domain.models import (
    BrandApplication,
    LayoutEnrichment,
    TextStyleSpec,
    TypographyCopy,
    TypographyPlan,
)


class DefaultTypographyPlanner:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_typography("planner.yaml", config_dir)
        self._templates = LayoutTemplateRegistry(config_dir)

    def plan(
        self,
        layout: LayoutEnrichment,
        copy: TypographyCopy,
        *,
        brand: BrandApplication | None = None,
        template_id: str = "default",
    ) -> TypographyPlan:
        roles = self._cfg.get("roles") or {}
        scale_cfg = self._cfg.get("scale_by_chars") or {}
        brand = brand or BrandApplication()
        template = self._templates.get(template_id)
        size_scale = min(layout.width / 1080.0, layout.height / 1350.0)
        styles: list[TextStyleSpec] = []
        copy_map = {
            "title": copy.headline,
            "subtitle": copy.subtitle,
            "cta": copy.cta,
            "footer": copy.footer or brand.footer_text,
            "logo": brand.brand_name,
        }
        # Prefer template layer order for hierarchy when available
        hierarchy = (
            tuple(r for r in template.layer_order if r in copy_map or r in ("icons", "illustration"))
            or layout.visual_hierarchy
        )
        for role, cfg in roles.items():
            if not isinstance(cfg, dict):
                continue
            base = float(cfg.get("base_size") or 24) * size_scale
            bias = (template.region_bias.get(role) or {}) if isinstance(template.region_bias, dict) else {}
            if isinstance(bias, dict) and bias.get("scale"):
                base *= float(bias["scale"])
            text = copy_map.get(role) or ""
            shrink = scale_cfg.get(role) or {}
            if text and shrink:
                soft = int(shrink.get("soft_limit") or 9999)
                if len(text) > soft:
                    base *= float(shrink.get("shrink_factor") or 0.9)
            min_f = float(self._cfg.get("min_font_size") or 18)
            max_f = float(self._cfg.get("max_font_size") or 96)
            base = max(min_f, min(max_f, base))
            family = brand.font_heading if role in ("title", "logo", "cta") else brand.font_body
            alignment = str(bias.get("align") or cfg.get("alignment") or "left")
            styles.append(
                TextStyleSpec(
                    role=role,
                    font_family=family,
                    font_size=round(base, 2),
                    font_weight=int(cfg.get("weight") or 400),
                    line_height=float(cfg.get("line_height") or 1.2),
                    letter_spacing=float(cfg.get("letter_spacing") or 0.0),
                    alignment=alignment,
                    color_token=str(cfg.get("color_token") or "text_primary"),
                )
            )
        return TypographyPlan(
            styles=tuple(styles),
            spacing_scale=size_scale,
            hierarchy=hierarchy,
            template_id=template.template_id,
            width=layout.width,
            height=layout.height,
            metadata={
                "roles": list(copy_map.keys()),
                "layer_order": list(template.layer_order),
                "preferred_layout": template.preferred_layout,
                "preferred_slide_type": template.preferred_slide_type,
            },
        )
