"""OpenAI Images API adapter — development pixel provider behind ImageProvider."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from openai import APIError, AsyncOpenAI, AuthenticationError, OpenAIError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.image.domain.models import ImageGenerationRequest, ImageGenerationResult

logger = get_logger(__name__)

_CONFIGS_DIR = Path(__file__).resolve().parents[3] / "configs"
_PROVIDER_CFG = _CONFIGS_DIR / "providers" / "openai.yaml"
_PRICING_CFG = _CONFIGS_DIR / "providers" / "pricing.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def map_size(width: int, height: int, cfg: dict[str, Any] | None = None) -> str:
    """Map request WxH to nearest GPT Image API size from openai.yaml."""
    data = cfg if cfg is not None else _load_yaml(_PROVIDER_CFG)
    ratio = (width / height) if height else 1.0
    for rule in data.get("size_map") or []:
        min_r = float(rule.get("min_ratio", 0.0))
        max_r = float(rule.get("max_ratio", 99.0))
        if min_r <= ratio < max_r or (max_r >= 99.0 and ratio >= min_r):
            size = str(rule.get("size") or "1024x1024")
            allowed = {str(s) for s in (data.get("allowed_sizes") or [])}
            if not allowed or size in allowed or size == "auto":
                return size
    return "1024x1024"


def estimate_image_cost(model: str, quality: str, *, pricing: dict[str, Any] | None = None) -> float:
    """USD estimate from pricing.yaml image_generation section."""
    data = pricing if pricing is not None else _load_yaml(_PRICING_CFG)
    section = (data.get("image_generation") or {}).get("openai") or {}
    models = section.get("models") or {}
    model_cfg = models.get(model) or models.get("default") or {}
    qualities = model_cfg.get("quality") or {}
    return float(qualities.get(quality) or qualities.get("medium") or 0.0)


class OpenAIImageProvider:
    """Calls OpenAI Images API. Switch via IMAGE_PROVIDER=openai. No local retries."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        provider_config: dict[str, Any] | None = None,
        pricing_config: dict[str, Any] | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = (api_key if api_key is not None else settings.OPENAI_API_KEY).strip()
        self._cfg = provider_config if provider_config is not None else _load_yaml(_PROVIDER_CFG)
        defaults = self._cfg.get("defaults") or {}
        self._model = (
            model
            or settings.OPENAI_IMAGE_MODEL
            or str(defaults.get("model") or "gpt-image-1")
        )
        self._defaults = defaults
        self._pricing = pricing_config if pricing_config is not None else _load_yaml(_PRICING_CFG)
        self._client = client

    def _require_key(self) -> None:
        if not self._api_key:
            raise AppError("OPENAI_API_KEY is required when IMAGE_PROVIDER=openai")

    def _get_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        self._require_key()
        return AsyncOpenAI(api_key=self._api_key)

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_key()
        started = time.perf_counter()
        params = dict(request.parameters or {})
        quality = str(
            params.get("quality") or self._defaults.get("quality") or "medium"
        ).lower()
        output_format = str(
            params.get("output_format") or self._defaults.get("output_format") or "png"
        ).lower()
        background = str(
            params.get("background") or self._defaults.get("background") or "auto"
        )
        moderation = str(
            params.get("moderation") or self._defaults.get("moderation") or "auto"
        )
        api_size = str(params.get("size") or map_size(request.width, request.height, self._cfg))
        model = str(params.get("model") or self._model)

        meta_in = dict(request.metadata or {})
        correlation_id = meta_in.get("correlation_id") or meta_in.get("request_id")

        client = self._get_client()
        try:
            # gpt-image has no native negative channel — fold bans into the prompt.
            prompt = request.prompt or ""
            neg = (request.negative_prompt or "").strip()
            if neg and "strictly avoid" not in prompt.lower() and "avoid:" not in prompt.lower():
                prompt = f"{prompt.rstrip()}. Strictly avoid: {neg}"

            create_kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "size": api_size,
                "quality": quality,
                "n": 1,
            }
            # gpt-image models use output_format; older dall-e uses response_format
            if model.startswith("gpt-image") or model.startswith("chatgpt-image"):
                create_kwargs["output_format"] = output_format
                if background:
                    create_kwargs["background"] = background
                if moderation:
                    create_kwargs["moderation"] = moderation
            else:
                create_kwargs["response_format"] = "b64_json"

            response = await client.images.generate(**create_kwargs)
        except AuthenticationError as exc:
            raise AppError(f"OpenAI authentication failed: {exc}") from exc
        except APIError as exc:
            raise AppError(f"OpenAI Images API error: {exc}") from exc
        except OpenAIError as exc:
            raise AppError(f"OpenAI Images API error: {exc}") from exc

        image_bytes = await self._extract_bytes(response)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = estimate_image_cost(model, quality, pricing=self._pricing)

        out_w, out_h = request.width, request.height
        if "x" in api_size and api_size != "auto":
            parts = api_size.split("x", 1)
            try:
                out_w, out_h = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass

        metadata: dict[str, Any] = {
            "style": request.style,
            "requested_size": f"{request.width}x{request.height}",
            "api_size": api_size,
            "quality": quality,
            "output_format": output_format,
            "image_byte_length": len(image_bytes),
        }
        if correlation_id:
            metadata["correlation_id"] = correlation_id
        if meta_in.get("request_id"):
            metadata["request_id"] = meta_in["request_id"]

        logger.info(
            "OpenAI image generated: model=%s size=%s quality=%s latency_ms=%d bytes=%d",
            model,
            api_size,
            quality,
            latency_ms,
            len(image_bytes),
        )

        return ImageGenerationResult(
            image_bytes=image_bytes,
            width=out_w,
            height=out_h,
            provider="openai",
            model=model,
            latency_ms=latency_ms,
            cost_estimate=cost,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
            metadata=metadata,
        )

    async def _extract_bytes(self, response: Any) -> bytes:
        data = getattr(response, "data", None) or []
        if not data:
            raise AppError("OpenAI Images API returned no image data")
        item = data[0]
        b64 = getattr(item, "b64_json", None)
        if b64:
            return base64.b64decode(b64)
        url = getattr(item, "url", None)
        if url:
            async with httpx.AsyncClient(timeout=60.0) as http:
                resp = await http.get(str(url))
                resp.raise_for_status()
                return resp.content
        raise AppError("OpenAI Images API response missing b64_json and url")
