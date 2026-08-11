"""Carousel renderers — consume DeckDefinition only (canonical SoT)."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw

from app.modules.carousel.domain.models import (
    DeckDefinition,
    RenderedDeck,
    RenderedSlide,
)

_ROOT = Path(__file__).resolve().parents[4]
_VIEWPORT = _ROOT / "configs" / "templates" / "carousel" / "viewport.html"


def _load_viewport() -> str:
    if _VIEWPORT.exists():
        return _VIEWPORT.read_text(encoding="utf-8")
    return (
        "<!DOCTYPE html><html><body style=\"width:{width}px;height:{height}px\">"
        "{svg_content}</body></html>"
    )


def _bind_viewport(width: int, height: int, svg_content: str) -> str:
    template = _load_viewport()
    return (
        template.replace("{width}", str(width))
        .replace("{height}", str(height))
        .replace("{svg_content}", svg_content)
    )


def _strip_xml_decl(svg: str) -> str:
    s = svg.strip()
    if s.startswith("<?xml"):
        end = s.find("?>")
        if end != -1:
            s = s[end + 2 :].lstrip()
    return s


class MockCarouselRenderer:
    """Deterministic renderer for CI — DeckDefinition only."""

    async def render(self, definition: DeckDefinition) -> RenderedDeck:
        w, h = definition.width, definition.height
        slides: list[RenderedSlide] = []
        for slide in definition.slides:
            svg = slide.svg_fragment or (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                f'<text x="40" y="80">{slide.title}</text></svg>'
            )
            html = _bind_viewport(w, h, _strip_xml_decl(svg))
            png = self._deterministic_png(slide.slide_id, slide.title, w, h)
            slides.append(
                RenderedSlide(
                    slide_id=slide.slide_id,
                    index=slide.index,
                    svg=svg,
                    png_bytes=png,
                    html_shell=html,
                    metadata={
                        "renderer": "mock",
                        "source_of_truth": "deck_definition",
                        "profile": definition.export_profile_id,
                    },
                )
            )
        return RenderedDeck(
            deck_id=definition.deck_id,
            slides=tuple(slides),
            width=w,
            height=h,
            metadata={
                "renderer": "mock",
                "editable_sot": "deck_definition",
                "definition_id": definition.definition_id,
            },
        )

    def _deterministic_png(self, slide_id: str, title: str, w: int, h: int) -> bytes:
        seed = hashlib.sha256(f"{slide_id}:{title}:{w}x{h}".encode()).digest()
        color = (seed[0], seed[1], seed[2])
        img = Image.new("RGB", (w, h), color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, w, 12], fill=(255, 255, 255))
        draw.text((48, 80), (title or "slide")[:60], fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


class PlaywrightCarouselRenderer:
    """Playwright adapter — HTML shell mounts DeckDefinition SVG."""

    async def render(self, definition: DeckDefinition) -> RenderedDeck:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return await MockCarouselRenderer().render(definition)

        w, h = definition.width, definition.height
        slides: list[RenderedSlide] = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": w, "height": h})
                for slide in definition.slides:
                    svg = slide.svg_fragment or (
                        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"></svg>'
                    )
                    html = _bind_viewport(w, h, _strip_xml_decl(svg))
                    await page.set_content(html, wait_until="domcontentloaded")
                    png = await page.screenshot(type="png", full_page=False)
                    slides.append(
                        RenderedSlide(
                            slide_id=slide.slide_id,
                            index=slide.index,
                            svg=svg if svg.startswith("<?xml") else f'<?xml version="1.0"?>\n{svg}',
                            png_bytes=png,
                            html_shell=html,
                            metadata={
                                "renderer": "playwright",
                                "source_of_truth": "deck_definition",
                            },
                        )
                    )
                await browser.close()
        except Exception:
            return await MockCarouselRenderer().render(definition)

        return RenderedDeck(
            deck_id=definition.deck_id,
            slides=tuple(slides),
            width=w,
            height=h,
            metadata={
                "renderer": "playwright",
                "editable_sot": "deck_definition",
                "definition_id": definition.definition_id,
            },
        )


class CarouselRenderer(PlaywrightCarouselRenderer):
    """Backward-compatible name; new path uses DeckDefinition."""

    async def render_slide(self, html: str, width: int, height: int) -> bytes:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": width, "height": height})
                await page.set_content(html, wait_until="networkidle")
                png = await page.screenshot(type="png", full_page=False)
                await browser.close()
                return png
        except Exception:
            img = Image.new("RGB", (width, height), "#0A1F2B")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    async def render_deck_pdf(self, slide_images: list[bytes]) -> bytes:
        images = [Image.open(io.BytesIO(b)).convert("RGB") for b in slide_images if b]
        if not images:
            return b""
        buf = io.BytesIO()
        images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
        return buf.getvalue()
