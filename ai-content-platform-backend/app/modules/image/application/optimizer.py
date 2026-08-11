"""Image optimization — compress, thumbnail, multi-format."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import OptimizedImageBundle


class DefaultImageOptimizer:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("optimize.yaml", config_dir)

    def optimize(self, image_bytes: bytes, *, width: int, height: int) -> OptimizedImageBundle:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if img.size != (width, height):
            img = img.resize((width, height), Image.Resampling.LANCZOS)

        opt_buf = io.BytesIO()
        img.save(opt_buf, format="PNG", optimize=True)
        optimized = opt_buf.getvalue()

        max_side = int(self._cfg.get("thumbnail_max_side") or 256)
        thumb = img.copy()
        thumb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        tbuf = io.BytesIO()
        thumb.save(tbuf, format="PNG", optimize=True)
        thumb_bytes = tbuf.getvalue()

        formats: dict[str, bytes] = {"png": optimized}
        if self._cfg.get("enable_jpeg", True):
            jbuf = io.BytesIO()
            img.save(jbuf, format="JPEG", quality=int(self._cfg.get("jpeg_quality") or 85), optimize=True)
            formats["jpeg"] = jbuf.getvalue()
        if self._cfg.get("enable_webp", True):
            wbuf = io.BytesIO()
            img.save(wbuf, format="WEBP", quality=int(self._cfg.get("webp_quality") or 80))
            formats["webp"] = wbuf.getvalue()

        return OptimizedImageBundle(
            original_bytes=image_bytes,
            optimized_bytes=optimized,
            thumbnail_bytes=thumb_bytes,
            width=width,
            height=height,
            thumb_width=thumb.size[0],
            thumb_height=thumb.size[1],
            formats=formats,
            metadata={"upscale_enabled": bool(self._cfg.get("upscale_enabled"))},
        )
