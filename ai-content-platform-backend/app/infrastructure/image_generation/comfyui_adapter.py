"""ComfyUI HTTP adapter — executes versioned workflows from the registry."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.image_generation.workflow_registry import FileComfyWorkflowRegistry
from app.modules.image.domain.models import ImageGenerationRequest, ImageGenerationResult
from app.modules.image.domain.ports import ComfyWorkflowRegistry

logger = get_logger(__name__)


class ComfyUIAdapter:
    """Calls a running ComfyUI instance. Switch via IMAGE_PROVIDER=comfyui."""

    provider_name = "comfyui"

    def __init__(
        self,
        base_url: str | None = None,
        registry: ComfyWorkflowRegistry | None = None,
        *,
        poll_interval_s: float = 0.5,
        max_polls: int = 120,
    ) -> None:
        settings = get_settings()
        self._base = (base_url or settings.COMFYUI_BASE_URL).rstrip("/")
        self._registry = registry or FileComfyWorkflowRegistry()
        self._poll_interval_s = poll_interval_s
        self._max_polls = max_polls

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        started = time.perf_counter()
        desc = self._registry.get(request.workflow_id, request.workflow_version)
        seed = request.seed if request.seed is not None else abs(hash(request.prompt)) % (2**31)
        params: dict[str, Any] = {
            "positive_prompt": request.prompt,
            "negative_prompt": request.negative_prompt or "text, watermark, logo, blurry",
            "width": request.width,
            "height": request.height,
            "seed": seed,
            **(request.parameters or {}),
        }
        graph = self._registry.render_graph(desc, params)  # type: ignore[attr-defined]
        client_id = str(uuid.uuid4())
        payload = {**graph, "client_id": client_id}
        # Comfy expects {"prompt": {...nodes...}} — ensure shape
        if "prompt" not in payload:
            payload = {"prompt": payload, "client_id": client_id}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(f"{self._base}/prompt", json=payload)
                resp.raise_for_status()
                body = resp.json()
            except httpx.HTTPError as exc:
                raise AppError(f"ComfyUI unavailable at {self._base}: {exc}") from exc

            prompt_id = str(body.get("prompt_id") or "")
            if not prompt_id:
                raise AppError("ComfyUI did not return prompt_id")

            image_bytes: bytes | None = None
            for _ in range(self._max_polls):
                await asyncio.sleep(self._poll_interval_s)
                hist = await client.get(f"{self._base}/history/{prompt_id}")
                if hist.status_code != 200:
                    continue
                data = hist.json()
                entry = data.get(prompt_id) or {}
                outputs = entry.get("outputs") or {}
                for node_out in outputs.values():
                    images = node_out.get("images") or []
                    if not images:
                        continue
                    img_meta = images[0]
                    fname = img_meta.get("filename")
                    subfolder = img_meta.get("subfolder") or ""
                    img_type = img_meta.get("type") or "output"
                    if not fname:
                        continue
                    img_resp = await client.get(
                        f"{self._base}/view",
                        params={"filename": fname, "subfolder": subfolder, "type": img_type},
                    )
                    img_resp.raise_for_status()
                    image_bytes = img_resp.content
                    break
                if image_bytes:
                    break

            if not image_bytes:
                raise AppError(
                    "ComfyUI prompt accepted but image was not available before timeout; "
                    "ensure the GPU host completes the workflow"
                )

        latency = int((time.perf_counter() - started) * 1000)
        return ImageGenerationResult(
            image_bytes=image_bytes,
            width=request.width,
            height=request.height,
            provider="comfyui",
            model=desc.model,
            latency_ms=latency,
            cost_estimate=None,
            workflow_id=desc.workflow_id,
            workflow_version=desc.version,
            metadata={"prompt_id": prompt_id, "seed": seed},
        )
