"""SVG Typography renderer — layered vector output; never early-rasterizes text."""

from __future__ import annotations

import html
import uuid
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from app.modules.typography.application.templates import LayoutTemplateRegistry
from app.modules.typography.domain.models import (
    BrandApplication,
    LayoutEnrichment,
    LogoPlacementOptions,
    SvgLayer,
    TypographyAsset,
    TypographyCopy,
    TypographyPlan,
    new_asset_id,
)


def _region_px(region: dict[str, Any] | None, width: int, height: int) -> tuple[float, float, float, float]:
    if not isinstance(region, dict):
        return 0.0, 0.0, 0.0, 0.0
    x = float(region.get("x") or 0.0) * width
    y = float(region.get("y") or 0.0) * height
    w = float(region.get("width") or 0.0) * width
    h = float(region.get("height") or 0.0) * height
    return x, y, w, h


def _resolve_color(brand: BrandApplication, token: str) -> str:
    if token == "text_primary":
        return brand.text_color
    if token == "accent":
        return brand.accent_color
    return str(brand.tokens.get(token) or brand.text_color)


def _token_radius(brand: BrandApplication, key: str = "lg", fallback: float = 12.0) -> float:
    if brand.design_tokens and brand.design_tokens.radius:
        val = brand.design_tokens.radius.get(key)
        if val is not None:
            return float(val)
    return fallback


def _token_opacity(brand: BrandApplication, key: str = "overlay", fallback: float = 0.72) -> float:
    if brand.design_tokens and brand.design_tokens.opacity:
        val = brand.design_tokens.opacity.get(key)
        if val is not None:
            return float(val)
    return fallback


def _token_spacing(brand: BrandApplication, key: str = "sm", fallback: float = 8.0) -> float:
    if brand.design_tokens and brand.design_tokens.spacing:
        val = brand.design_tokens.spacing.get(key)
        if val is not None:
            return float(val)
    return fallback


def _logo_box(
    *,
    width: int,
    height: int,
    options: LogoPlacementOptions,
) -> tuple[float, float, float, float]:
    size_frac = {"s": 0.08, "m": 0.12, "l": 0.18}.get(options.size.lower(), 0.12)
    side = min(width, height) * size_frac
    margin = min(width, height) * max(0.0, options.margin)
    if options.safe_area:
        margin = max(margin, min(width, height) * 0.03)
    pos = options.position
    if pos == "custom" and options.custom_x is not None and options.custom_y is not None:
        x = options.custom_x * width
        y = options.custom_y * height
    elif pos == "top_left":
        x, y = margin, margin
    elif pos == "bottom_left":
        x, y = margin, height - side - margin
    elif pos == "bottom_right":
        x, y = width - side - margin, height - side - margin
    elif pos == "center":
        x, y = (width - side) / 2, (height - side) / 2
    else:  # top_right default
        x, y = width - side - margin, margin
    return x, y, side, side


class DefaultTypographyRenderer:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._templates = LayoutTemplateRegistry(config_dir)

    def render(
        self,
        *,
        layout: LayoutEnrichment,
        plan: TypographyPlan,
        brand: BrandApplication,
        copy: TypographyCopy,
        illustration_ref: str = "",
        logo_options: LogoPlacementOptions | None = None,
        logo_data_uri: str | None = None,
    ) -> TypographyAsset:
        logo_options = logo_options or LogoPlacementOptions()
        w, h = plan.width, plan.height
        plan_map = layout.layout_plan
        style_by_role = {s.role: s for s in plan.styles}
        template = self._templates.get(plan.template_id)
        layers_by_role: dict[str, list[SvgLayer]] = {}
        layer_elems: dict[str, list[Any]] = {}

        svg = Element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "width": str(w),
                "height": str(h),
                "viewBox": f"0 0 {w} {h}",
                "role": "img",
            },
        )
        defs = SubElement(svg, "defs")
        SubElement(
            defs,
            "style",
        ).text = (
            f".font-heading{{font-family:'{brand.font_heading}',system-ui,sans-serif}}"
            f".font-body{{font-family:'{brand.font_body}',system-ui,sans-serif}}"
        )

        z_base = {
            "illustration": 0,
            "title_bg": 10,
            "title": 20,
            "subtitle": 30,
            "cta": 40,
            "footer": 50,
            "logo": 60,
            "icons": 70,
        }

        if illustration_ref:
            SubElement(
                svg,
                "image",
                {
                    "id": "layer-illustration",
                    "href": illustration_ref,
                    "x": "0",
                    "y": "0",
                    "width": str(w),
                    "height": str(h),
                    "preserveAspectRatio": "xMidYMid slice",
                },
            )
            layers_by_role.setdefault("illustration", []).append(
                SvgLayer(
                    layer_id="illustration",
                    kind="image",
                    role="illustration",
                    content=illustration_ref,
                    x=0,
                    y=0,
                    width=float(w),
                    height=float(h),
                    parent=None,
                    constraints={"fit": "cover"},
                    z_index=z_base["illustration"],
                    anchor="top_left",
                    visibility="visible",
                    animation={},
                    metadata={"vector_text": False},
                )
            )

        texts = {
            "title": copy.headline,
            "subtitle": copy.subtitle,
            "cta": copy.cta,
            "footer": copy.footer or brand.footer_text,
            "logo": brand.brand_name if logo_options.include_logo else "",
        }
        pad = _token_spacing(brand, "sm", 8.0)
        radius = _token_radius(brand, "lg", 12.0)
        overlay_op = _token_opacity(brand, "overlay", 0.72)

        for role, text in texts.items():
            if not text:
                continue
            region = plan_map.get(role) if isinstance(plan_map.get(role), dict) else None
            x, y, rw, rh = _region_px(region, w, h)
            bias = template.region_bias.get(role) if isinstance(template.region_bias, dict) else {}
            if isinstance(bias, dict):
                if bias.get("y_bias") is not None:
                    y = float(bias["y_bias"]) * h
                if bias.get("x_bias") is not None:
                    x = float(bias["x_bias"]) * w
                if bias.get("width_bias") is not None:
                    rw = float(bias["width_bias"]) * w
            if rw <= 0 or rh <= 0:
                defaults = {
                    "title": (0.08 * w, 0.68 * h, 0.84 * w, 0.10 * h),
                    "subtitle": (0.08 * w, 0.78 * h, 0.84 * w, 0.06 * h),
                    "cta": (0.08 * w, 0.86 * h, 0.50 * w, 0.06 * h),
                    "footer": (0.08 * w, 0.93 * h, 0.84 * w, 0.05 * h),
                    "logo": (0.78 * w, 0.04 * h, 0.14 * w, 0.08 * h),
                }
                x, y, rw, rh = defaults.get(role, (40, 40, w - 80, 60))

            if role == "logo":
                x, y, rw, rh = _logo_box(width=w, height=h, options=logo_options)
                layer_id = f"logo-{uuid.uuid4().hex[:8]}"
                if logo_data_uri:
                    img_attrs = {
                        "id": layer_id,
                        "href": logo_data_uri,
                        "x": str(x),
                        "y": str(y),
                        "width": str(rw),
                        "height": str(rh),
                        "preserveAspectRatio": "xMidYMid meet",
                        "opacity": str(max(0.0, min(1.0, logo_options.opacity))),
                    }
                    SubElement(svg, "image", img_attrs)
                    layers_by_role.setdefault("logo", []).append(
                        SvgLayer(
                            layer_id=layer_id,
                            kind="logo",
                            role="logo",
                            content=brand.logo_object_key or "logo",
                            x=x,
                            y=y,
                            width=rw,
                            height=rh,
                            parent=None,
                            constraints={"composited_from_storage": True},
                            z_index=z_base["logo"],
                            anchor="top_left",
                            visibility="visible",
                            animation={},
                            style={"opacity": logo_options.opacity},
                            metadata={
                                "include_logo": True,
                                "position": logo_options.position,
                                "size": logo_options.size,
                                "from_storage": True,
                            },
                        )
                    )
                    continue
                # Fallback: brand name text when no storage logo bytes
                pass

            style = style_by_role.get(role)
            font_size = style.font_size if style else 24.0
            weight = style.font_weight if style else 400
            color = _resolve_color(brand, style.color_token if style else "text_primary")
            align = style.alignment if style else "left"
            font_class = "font-heading" if role in ("title", "logo", "cta") else "font-body"
            layer_id = f"{role}-{uuid.uuid4().hex[:8]}"
            parent_id: str | None = None

            if role == "title":
                bg_id = f"title-bg-{uuid.uuid4().hex[:8]}"
                parent_id = bg_id
                SubElement(
                    svg,
                    "rect",
                    {
                        "id": bg_id,
                        "x": str(x - pad),
                        "y": str(y - pad),
                        "width": str(rw + pad * 2),
                        "height": str(rh + pad * 2),
                        "rx": str(radius),
                        "fill": brand.primary_color,
                        "fill-opacity": str(overlay_op),
                    },
                )
                layers_by_role.setdefault("title_bg", []).append(
                    SvgLayer(
                        layer_id=bg_id,
                        kind="shape",
                        role="title_bg",
                        x=x - pad,
                        y=y - pad,
                        width=rw + pad * 2,
                        height=rh + pad * 2,
                        parent=None,
                        constraints={"bound_to": "title"},
                        z_index=z_base["title_bg"],
                        anchor="top_left",
                        visibility="visible",
                        animation={},
                        style={"fill": brand.primary_color, "rx": radius},
                    )
                )

            text_anchor = "start"
            tx = x
            if align == "center":
                text_anchor = "middle"
                tx = x + rw / 2
            elif align == "right":
                text_anchor = "end"
                tx = x + rw

            el = SubElement(
                svg,
                "text",
                {
                    "id": layer_id,
                    "class": font_class,
                    "x": str(tx),
                    "y": str(y + font_size),
                    "fill": color,
                    "font-size": str(font_size),
                    "font-weight": str(weight),
                    "text-anchor": text_anchor,
                    "letter-spacing": str((style.letter_spacing if style else 0) * font_size),
                },
            )
            max_chars = max(12, int(rw / max(font_size * 0.5, 1)))
            lines = _wrap_words(text, max_chars)
            for i, line in enumerate(lines[:4]):
                tspan = SubElement(
                    el,
                    "tspan",
                    {
                        "x": str(tx),
                        "dy": "0" if i == 0 else str(font_size * (style.line_height if style else 1.2)),
                    },
                )
                tspan.text = html.escape(line)

            layers_by_role.setdefault(role, []).append(
                SvgLayer(
                    layer_id=layer_id,
                    kind="text" if role != "logo" else "logo",
                    role=role,
                    content=text,
                    x=x,
                    y=y,
                    width=rw,
                    height=rh,
                    parent=parent_id,
                    constraints={"max_lines": 4, "wrap": True},
                    z_index=z_base.get(role, 25),
                    anchor="top_left" if align == "left" else align,
                    visibility="visible",
                    animation={},
                    style={
                        "font_size": font_size,
                        "font_weight": weight,
                        "fill": color,
                        "alignment": align,
                        "font_family": style.font_family if style else brand.font_body,
                    },
                    metadata={"vector_text": True, "never_rasterized_early": True},
                )
            )
            layer_elems.setdefault(role, []).append(el)

        icons = plan_map.get("icon_regions") or []
        for i, icon in enumerate(icons[:4]):
            if not isinstance(icon, dict):
                continue
            ix, iy, iw, ih = _region_px(icon, w, h)
            icon_id = f"icon-{i}"
            SubElement(
                svg,
                "circle",
                {
                    "id": icon_id,
                    "cx": str(ix + iw / 2),
                    "cy": str(iy + ih / 2),
                    "r": str(min(iw, ih) / 2),
                    "fill": "none",
                    "stroke": brand.accent_color,
                    "stroke-width": "2",
                },
            )
            layers_by_role.setdefault("icons", []).append(
                SvgLayer(
                    layer_id=icon_id,
                    kind="icon",
                    role=f"icon_{i}",
                    x=ix,
                    y=iy,
                    width=iw,
                    height=ih,
                    parent=None,
                    constraints={"aspect": "1:1"},
                    z_index=z_base["icons"] + i,
                    anchor="center",
                    visibility="visible",
                    animation={},
                    style={"stroke": brand.accent_color},
                )
            )

        # Honor template layer order for metadata sequence
        ordered: list[SvgLayer] = []
        seen: set[str] = set()
        for key in template.layer_order:
            for layer in layers_by_role.get(key, []):
                ordered.append(layer)
                seen.add(layer.layer_id)
        for key, group in layers_by_role.items():
            for layer in group:
                if layer.layer_id not in seen:
                    ordered.append(layer)
                    seen.add(layer.layer_id)

        svg_bytes = tostring(svg, encoding="unicode")
        return TypographyAsset(
            asset_id=new_asset_id(),
            svg=svg_bytes
            if svg_bytes.startswith("<?xml")
            else f'<?xml version="1.0" encoding="UTF-8"?>\n{svg_bytes}',
            layers=tuple(ordered),
            width=w,
            height=h,
            layout=layout,
            typography_plan=plan,
            brand=brand,
            illustration_ref=illustration_ref,
            metadata={
                "renderer": "svg_layers",
                "primary_format": "svg",
                "template_id": template.template_id,
                "layer_order": list(template.layer_order),
            },
        )


def _wrap_words(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
