"""Google Gemini native image generation adapter — calls generativeLanguage REST API."""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.image.domain.models import ImageGenerationRequest, ImageGenerationResult

logger = get_logger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_CONFIGS_DIR = Path(__file__).resolve().parents[3] / "configs"
_PRICING_CFG = _CONFIGS_DIR / "providers" / "pricing.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def estimate_image_cost(model: str, quality: str, *, pricing: dict[str, Any] | None = None) -> float:
    data = pricing if pricing is not None else _load_yaml(_PRICING_CFG)
    section = (data.get("image_generation") or {}).get("gemini") or {}
    models = section.get("models") or {}
    model_cfg = models.get(model) or models.get("default") or {}
    qualities = model_cfg.get("quality") or {}
    return float(qualities.get(quality) or qualities.get("medium") or 0.0)


class GeminiImageProvider:
    """Calls Gemini's native image generation (generateContent + responseModalities)."""

    provider_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = _BASE_URL,
        pricing_config: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = (api_key if api_key is not None else settings.GEMINI_API_KEY).strip()
        self._model = model or settings.GEMINI_IMAGE_MODEL
        self._base_url = base_url.rstrip("/")
        self._pricing = pricing_config if pricing_config is not None else _load_yaml(_PRICING_CFG)
        self._client = client

    def _require_key(self) -> None:
        if not self._api_key:
            raise AppError("GEMINI_API_KEY is required when IMAGE_PROVIDER=gemini")

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_key()
        started = time.perf_counter()
        params = dict(request.parameters or {})
        model = str(params.get("model") or self._model)

        prompt = request.prompt or ""
        neg = (request.negative_prompt or "").strip()
        if neg and "strictly avoid" not in prompt.lower() and "avoid:" not in prompt.lower():
            prompt = f"{prompt.rstrip()}. Strictly avoid: {neg}"

        url = f"{self._base_url}/models/{model}:generateContent?key={self._api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }

        meta_in = dict(request.metadata or {})
        correlation_id = meta_in.get("correlation_id") or meta_in.get("request_id")

        client = self._client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=90.0)
        try:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AppError(f"Gemini image generation error: {exc.response.text[:500]}") from exc
        except httpx.HTTPError as exc:
            raise AppError(f"Gemini image generation error: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

        data = resp.json()
        image_bytes = self._extract_bytes(data)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = estimate_image_cost(model, "medium", pricing=self._pricing)

        out_w, out_h = request.width, request.height
        try:
            from PIL import Image

            with Image.open(io.BytesIO(image_bytes)) as img:
                out_w, out_h = img.size
        except Exception:  # noqa: BLE001 — dimension probing is best-effort
            pass

        metadata: dict[str, Any] = {
            "style": request.style,
            "requested_size": f"{request.width}x{request.height}",
            "image_byte_length": len(image_bytes),
        }
        if correlation_id:
            metadata["correlation_id"] = correlation_id
        if meta_in.get("request_id"):
            metadata["request_id"] = meta_in["request_id"]

        logger.info(
            "Gemini image generated: model=%s latency_ms=%d bytes=%d",
            model,
            latency_ms,
            len(image_bytes),
        )

        return ImageGenerationResult(
            image_bytes=image_bytes,
            width=out_w,
            height=out_h,
            provider=self.provider_name,
            model=model,
            latency_ms=latency_ms,
            cost_estimate=cost,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
            metadata=metadata,
        )

    def _extract_bytes(self, data: dict[str, Any]) -> bytes:
        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise AppError(
                f"Gemini returned no candidates (blockReason={block_reason})"
                if block_reason
                else "Gemini image generation returned no candidates"
            )
        parts = (candidates[0].get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
        text_parts = [p.get("text") for p in parts if p.get("text")]
        raise AppError(
            "Gemini response contained no image data"
            + (f" (text: {' '.join(text_parts)[:200]})" if text_parts else "")
        )
