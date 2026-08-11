"""Deterministic mock image generator for GPU-optional delivery."""

from __future__ import annotations

import io
import time

from PIL import Image, ImageDraw

from app.modules.image.domain.models import ImageGenerationRequest, ImageGenerationResult


class MockImageGenerator:
    """Produces a consulting-style illustration placeholder (navy/blue gradients)."""

    provider_name = "mock"

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        started = time.perf_counter()
        width, height = request.width, request.height
        img = Image.new("RGB", (width, height), "#0A1F2B")
        draw = ImageDraw.Draw(img)

        for i in range(0, height, 8):
            ratio = i / height
            r = int(10 + ratio * 30)
            g = int(31 + ratio * 40)
            b = int(43 + ratio * 80)
            draw.rectangle([0, i, width, i + 8], fill=(r, g, b))

        cx, cy = width // 2, height // 2 - 80
        draw.ellipse([cx - 180, cy - 180, cx + 180, cy + 180], outline="#4A90C8", width=3)
        draw.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], outline="#7EB6D9", width=2)
        # Safe area cue (no text overlay — illustration only)
        draw.rectangle([60, height - 200, width - 60, height - 60], outline="#1A5CB0", width=2)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        latency = int((time.perf_counter() - started) * 1000)
        return ImageGenerationResult(
            image_bytes=buf.getvalue(),
            width=width,
            height=height,
            provider="mock",
            model="mock-gradient-v1",
            latency_ms=latency,
            cost_estimate=0.0,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
            metadata={"style": request.style},
        )
