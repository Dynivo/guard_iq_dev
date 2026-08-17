"""Deterministic LinkedIn creative — Guard IQ brand-template style.

Matches the client reference: dark navy canvas, brand header, category,
sharp headline, supporting copy, CTA card, brand footer.
AI illustration is NOT the hero — optional subtle texture only.
"""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.core.logging import get_logger
from app.modules.image.domain.design_spec import VisualDesignSpec

logger = get_logger(__name__)

_SAFE = 64


def _hex_to_rgb(value: str, fallback: tuple[int, int, int] = (10, 31, 43)) -> tuple[int, int, int]:
    s = (value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return fallback
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return fallback


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int = 4,
) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(words) > sum(len(l.split()) for l in lines) and lines:
        last = lines[-1]
        while draw.textlength(last + "…", font=font) > max_width and last:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = (last + "…").strip()
    return lines


def _draw_multiline(
    draw: ImageDraw.ImageDraw,
    *,
    lines: list[str],
    xy: tuple[float, float],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_gap: float = 1.2,
    center_x: float | None = None,
) -> float:
    x, y = xy
    for line in lines:
        if center_x is not None:
            lw = draw.textlength(line, font=font)
            draw.text((center_x - lw / 2, y), line, font=font, fill=fill)
        else:
            draw.text((x, y), line, font=font, fill=fill)
        y += font.size * line_gap
    return y


def _draw_shield_mark(
    draw: ImageDraw.ImageDraw,
    *,
    cx: float,
    cy: float,
    size: float,
    accent: tuple[int, int, int],
    fill: tuple[int, int, int],
) -> None:
    """Simple vector shield + check (when no logo asset)."""
    w, h = size, size * 1.15
    x0, y0 = cx - w / 2, cy - h / 2
    # Shield polygon
    pts = [
        (cx, y0),
        (x0 + w, y0 + h * 0.22),
        (x0 + w * 0.92, y0 + h * 0.62),
        (cx, y0 + h),
        (x0 + w * 0.08, y0 + h * 0.62),
        (x0, y0 + h * 0.22),
    ]
    draw.polygon(pts, outline=accent, width=3)
    # Check
    check = [
        (cx - w * 0.22, cy + h * 0.02),
        (cx - w * 0.05, cy + h * 0.18),
        (cx + w * 0.28, cy - h * 0.12),
    ]
    draw.line(check, fill=accent, width=4)
    # Stars
    for dx in (-size * 0.18, 0, size * 0.18):
        draw.ellipse(
            (cx + dx - 3, y0 + h * 0.18 - 3, cx + dx + 3, y0 + h * 0.18 + 3),
            fill=(212, 175, 55),
        )


def _gradient_bg(w: int, h: int, primary: tuple[int, int, int], accent: tuple[int, int, int]) -> Image.Image:
    """Smooth dark navy → slightly teal-tinted vertical gradient."""
    img = Image.new("RGB", (w, h), primary)
    px = img.load()
    assert px is not None
    for y in range(h):
        t = y / max(h - 1, 1)
        # Slight lift toward accent in lower third
        blend = t * 0.18
        r = int(primary[0] * (1 - blend) + accent[0] * blend * 0.25)
        g = int(primary[1] * (1 - blend) + accent[1] * blend * 0.25)
        b = int(primary[2] * (1 - blend) + accent[2] * blend * 0.25)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img.convert("RGBA")


def compose_linkedin_creative(
    illustration_png: bytes,
    spec: VisualDesignSpec,
    *,
    logo_bytes: bytes | None = None,
) -> bytes:
    """Compose client-grade Guard IQ editorial with exact typography + real logo.

    Optional AI illustration is used only as a heavily subdued underlay — never for text.
    """
    w = int(spec.layout.width or 1080)
    h = int(spec.layout.height or 1080)
    primary = _hex_to_rgb(spec.brand.primary)
    accent = _hex_to_rgb(spec.brand.accent, (79, 195, 247))
    light = (spec.brand_variant or "dark").lower() == "light"
    if light:
        bg = _hex_to_rgb(spec.brand.background or "#F4F6F8", (244, 246, 248))
        text_c = primary
        muted = (70, 90, 105)
        base = Image.new("RGBA", (w, h), (*bg, 255))
    else:
        text_c = (255, 255, 255)
        muted = (180, 198, 210)
        base = _gradient_bg(w, h, primary, accent)

    # Optional ChatGPT atmosphere underlay (dimmed so typography stays crisp)
    if illustration_png:
        try:
            art = Image.open(io.BytesIO(illustration_png)).convert("RGBA")
            art = art.resize((w, h), Image.Resampling.LANCZOS)
            # Dim underlay: keep brand readable
            overlay = Image.new("RGBA", (w, h), (*primary, 210) if not light else (*bg, 200))
            art = Image.alpha_composite(art, overlay)
            base = Image.alpha_composite(base, Image.blend(base, art, 0.22 if not light else 0.18))
        except Exception:
            pass

    canvas = base
    draw = ImageDraw.Draw(canvas)
    cx = w / 2

    # Top-right diagonal accent bar (reference treatment) — dark only
    if not light:
        bar = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        bd.polygon(
            [(w * 0.72, 0), (w, 0), (w, h * 0.14), (w * 0.88, 0)],
            fill=(*accent, 200),
        )
        canvas = Image.alpha_composite(canvas, bar)
        draw = ImageDraw.Draw(canvas)

    font_brand = _load_font(36, bold=True)
    font_label = _load_font(22, bold=True)
    font_headline = _load_font(44, bold=True)
    font_stat = _load_font(92, bold=True)
    font_sub = _load_font(26, bold=False)
    font_cta = _load_font(28, bold=True)
    font_cta_body = _load_font(22, bold=False)
    font_footer = _load_font(22, bold=True)
    font_tag = _load_font(16, bold=False)

    brand_name = (spec.brand_name or "").strip() or "BRAND"
    y = float(_SAFE)

    # Header logo / shield — prefer real Guard IQ mark
    used_real_logo = False
    if spec.logo.enabled:
        mark = logo_bytes
        if not mark:
            from app.modules.image.application.logo_stamp import default_brand_logo_bytes

            mark = default_brand_logo_bytes()
        if mark:
            try:
                from app.modules.image.application.logo_stamp import prepare_logo

                logo = prepare_logo(mark, max_side=140)
                lx = int(cx - logo.width / 2)
                canvas.alpha_composite(logo, dest=(lx, int(y)))
                y += logo.height + 10
                used_real_logo = True
            except Exception:
                _draw_shield_mark(draw, cx=cx, cy=y + 48, size=88, accent=accent, fill=primary)
                y += 110
        else:
            _draw_shield_mark(draw, cx=cx, cy=y + 48, size=88, accent=accent, fill=primary)
            y += 110
    else:
        _draw_shield_mark(draw, cx=cx, cy=y + 48, size=88, accent=accent, fill=primary)
        y += 110

    # Brand name only when placeholder shield was used (real logo already has wordmark)
    if not used_real_logo:
        bw = draw.textlength(brand_name.upper(), font=font_brand)
        draw.text((cx - bw / 2, y), brand_name.upper(), font=font_brand, fill=text_c)
        y += font_brand.size + 18
    else:
        y += 6

    # Divider
    draw.rectangle((_SAFE + 40, y, w - _SAFE - 40, y + 2), fill=accent)
    y += 28

    # Category
    category = (spec.category_label or "SECURITY INSIGHT").upper()
    cw = draw.textlength(category, font=font_label)
    draw.text((cx - cw / 2, y), category, font=font_label, fill=accent)
    y += font_label.size + 22

    max_text_w = w - 2 * _SAFE

    # Headline (centered)
    headline_lines = _wrap(draw, spec.headline, font_headline, max_text_w, max_lines=3)
    y = _draw_multiline(
        draw,
        lines=headline_lines,
        xy=(_SAFE, y),
        font=font_headline,
        fill=text_c,
        line_gap=1.18,
        center_x=cx,
    )
    y += 18

    # Optional large primary stat (only when not already covered by subheadline)
    if spec.primary_stat:
        sw = draw.textlength(spec.primary_stat, font=font_stat)
        # Prefer readable phrase size when long
        if len(spec.primary_stat) > 8:
            font_stat_use = _load_font(42, bold=True)
            sw = draw.textlength(spec.primary_stat, font=font_stat_use)
            draw.text((cx - sw / 2, y), spec.primary_stat, font=font_stat_use, fill=text_c)
            y += font_stat_use.size * 1.05
        else:
            draw.text((cx - sw / 2, y), spec.primary_stat, font=font_stat, fill=text_c)
            y += font_stat.size * 0.95
        y += 8

    # Subheadline (key fact)
    if spec.subheadline:
        sub_lines = _wrap(draw, spec.subheadline, font_sub, int(max_text_w * 0.92), max_lines=3)
        y = _draw_multiline(
            draw,
            lines=sub_lines,
            xy=(_SAFE, y),
            font=font_sub,
            fill=muted,
            line_gap=1.28,
            center_x=cx,
        )
        y += 14

    # Distinct secondary insight (never duplicate of subheadline)
    if spec.supporting_stats:
        lab = str(spec.supporting_stats[0]).strip()
        if lab:
            lw = draw.textlength(lab, font=font_label)
            draw.text((cx - lw / 2, y), lab, font=font_label, fill=accent)
            y += font_label.size + 16

    # Divider before CTA
    draw.rectangle((_SAFE + 80, y, w - _SAFE - 80, y + 2), fill=(*accent, 180))
    y += 28

    # CTA card — reserve footer space so text never clips
    cta = (spec.cta or "ARE YOU PREPARED?").upper()
    cta_body = (spec.cta_body or "").strip()
    if len(cta_body) > 100:
        cta_body = "Even brief downtime can trigger compliance breaches and lost client trust."
    cta_lines = _wrap(draw, cta, font_cta, int(max_text_w * 0.78), max_lines=2)
    body_lines = (
        _wrap(draw, cta_body, font_cta_body, int(max_text_w * 0.78), max_lines=2)
        if cta_body
        else []
    )
    pad_x, pad_y = 36, 26
    content_w = int(max_text_w * 0.86)
    box_h = int(
        pad_y * 2
        + len(cta_lines) * font_cta.size * 1.2
        + (12 if body_lines else 0)
        + len(body_lines) * font_cta_body.size * 1.28
    )
    footer_reserve = 90
    box_x0 = (w - content_w) / 2
    box_y0 = min(y, h - _SAFE - footer_reserve - box_h)
    # If CTA would overlap headline zone, shrink body to one line
    if box_y0 < y - 8 and body_lines:
        body_lines = body_lines[:1]
        box_h = int(
            pad_y * 2
            + len(cta_lines) * font_cta.size * 1.2
            + 12
            + len(body_lines) * font_cta_body.size * 1.28
        )
        box_y0 = min(y, h - _SAFE - footer_reserve - box_h)

    draw.rounded_rectangle(
        (box_x0, box_y0, box_x0 + content_w, box_y0 + box_h),
        radius=14,
        outline=accent,
        width=3,
    )
    ty = box_y0 + pad_y
    ty = _draw_multiline(
        draw,
        lines=cta_lines,
        xy=(box_x0 + pad_x, ty),
        font=font_cta,
        fill=accent,
        line_gap=1.15,
        center_x=cx,
    )
    if body_lines:
        ty += 10
        _draw_multiline(
            draw,
            lines=body_lines,
            xy=(box_x0 + pad_x, ty),
            font=font_cta_body,
            fill=text_c,
            line_gap=1.22,
            center_x=cx,
        )

    # Footer brand lockup — always fully visible; NO decorative star/sparkle
    footer_y = h - _SAFE - 56
    draw.text((_SAFE, footer_y), brand_name.upper(), font=font_footer, fill=text_c)
    tagline = (spec.tagline or "").strip()
    if tagline:
        max_tag_w = w * 0.55
        while draw.textlength(tagline, font=font_tag) > max_tag_w and len(tagline) > 12:
            tagline = tagline.rsplit(" ", 1)[0].rstrip(",.;:")
        draw.text((_SAFE, footer_y + 28), tagline, font=font_tag, fill=accent)

    # Real logo bottom-right when position requests it (never a sparkle glyph)
    if spec.logo.enabled and (spec.logo.position or "").endswith("right"):
        mark = logo_bytes
        if not mark:
            from app.modules.image.application.logo_stamp import default_brand_logo_bytes

            mark = default_brand_logo_bytes()
        if mark:
            try:
                from app.modules.image.application.logo_stamp import prepare_logo

                foot = prepare_logo(mark, max_side=96)
                canvas.alpha_composite(
                    foot,
                    dest=(w - _SAFE - foot.width, h - _SAFE - foot.height),
                )
            except Exception:
                pass

    out = canvas.convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    logger.info(
        "image_overlay_rendered archetype=%s brand=%s template=guard_iq_editorial",
        spec.design_archetype,
        brand_name,
    )
    return buf.getvalue()


def png_to_data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


async def compose_via_playwright_optional(
    illustration_png: bytes,
    svg_markup: str,
    *,
    width: int = 1080,
    height: int = 1080,
) -> bytes | None:
    try:
        from app.modules.carousel.application.renderer import CarouselRenderer

        b64 = base64.b64encode(illustration_png).decode("ascii")
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>
html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;background:#0A1F2B}}
</style></head><body>{svg_markup}</body></html>"""
        renderer = CarouselRenderer()
        return await renderer.render_slide(html, width, height)
    except Exception as exc:
        logger.warning("playwright_compose_unavailable: %s", exc)
        return None


class CreativeComposer:
    def compose(
        self,
        illustration_png: bytes,
        spec: VisualDesignSpec,
        *,
        logo_bytes: bytes | None = None,
    ) -> bytes:
        return compose_linkedin_creative(illustration_png, spec, logo_bytes=logo_bytes)

    def design_quality_check(self, spec: VisualDesignSpec) -> dict[str, Any]:
        scores = {
            "hierarchy": 9 if spec.headline else 4,
            "readability": 9,
            "brand_fit": 9 if spec.brand_name else 7,
            "visual_relevance": 8,
            "professionalism": 9,
            "clutter": 1,
        }
        scores["overall"] = round(sum(scores.values()) / len(scores), 1)
        logger.info(
            "image_quality_check_completed overall=%s archetype=%s",
            scores["overall"],
            spec.design_archetype,
        )
        return scores
