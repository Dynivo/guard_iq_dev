"""Gemini native image generation adapter for the gemini_infographic pipeline only.

Deliberately a separate class/provider key from GeminiImageProvider
(gemini_provider.py) — that one keeps serving the existing alert_card
("blue card") flow via the raw REST call unchanged. This one uses the
official google-genai SDK, config-driven model/aspect/quality-tier
resolution, and reference-image support, and is registered under the
"gemini_infographic" provider key so it can never be picked up by the
existing IMAGE_PROVIDER=gemini selection.
"""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.image.domain.models import ImageGenerationRequest, ImageGenerationResult

logger = get_logger(__name__)

_CONFIGS_DIR = Path(__file__).resolve().parents[3] / "configs"
_PROVIDER_CFG = _CONFIGS_DIR / "providers" / "gemini_image.yaml"
_PRICING_CFG = _CONFIGS_DIR / "providers" / "pricing.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def map_aspect_ratio(width: int, height: int, cfg: dict[str, Any] | None = None) -> str:
    """Map request WxH to nearest Gemini aspect_ratio from gemini_image.yaml."""
    data = cfg if cfg is not None else _load_yaml(_PROVIDER_CFG)
    ratio = (width / height) if height else 1.0
    for rule in data.get("aspect_map") or []:
        min_r = float(rule.get("min_ratio", 0.0))
        max_r = float(rule.get("max_ratio", 99.0))
        if min_r <= ratio < max_r or (max_r >= 99.0 and ratio >= min_r):
            aspect = str(rule.get("aspect_ratio") or "1:1")
            allowed = {str(a) for a in (data.get("allowed_aspect_ratios") or [])}
            if not allowed or aspect in allowed:
                return aspect
    return "1:1"


def resolve_gemini_model(
    *,
    quality_tier: str | None = None,
    explicit_model: str | None = None,
    cfg: dict[str, Any] | None = None,
    settings: Any | None = None,
) -> str:
    """Resolve model id from quality tier / request / settings (never hardcode in callers)."""
    data = cfg if cfg is not None else _load_yaml(_PROVIDER_CFG)
    models = data.get("models") or {}
    defaults = data.get("defaults") or {}
    s = settings or get_settings()
    if explicit_model and str(explicit_model).strip():
        return str(explicit_model).strip()
    tier = (quality_tier or "").strip().lower()
    if tier in {"premium", "pro", "high"}:
        return str(
            getattr(s, "GEMINI_IMAGE_MODEL_PREMIUM", None)
            or models.get("premium")
            or "gemini-3-pro-image"
        )
    return str(
        getattr(s, "GEMINI_IMAGE_MODEL", None)
        or models.get("standard")
        or defaults.get("model")
        or "gemini-3.1-flash-image"
    )


def estimate_gemini_image_cost(
    model: str,
    quality_tier: str,
    *,
    pricing: dict[str, Any] | None = None,
) -> float:
    data = pricing if pricing is not None else _load_yaml(_PRICING_CFG)
    section = (data.get("image_generation") or {}).get("gemini") or {}
    models = section.get("models") or {}
    model_cfg = models.get(model) or models.get("default") or {}
    tiers = model_cfg.get("quality") or model_cfg.get("tiers") or {}
    return float(
        tiers.get(quality_tier)
        or tiers.get("standard")
        or tiers.get("premium")
        or section.get("default_cost")
        or 0.04
    )


def _extract_inline_image_bytes(response: Any) -> bytes:
    """Pull first inline image payload from google.genai response parts."""
    parts: list[Any] = []
    if hasattr(response, "parts") and response.parts:
        parts = list(response.parts)
    elif getattr(response, "candidates", None):
        for cand in response.candidates or []:
            content = getattr(cand, "content", None)
            cand_parts = getattr(content, "parts", None) if content else None
            if cand_parts:
                parts.extend(list(cand_parts))

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline is None and isinstance(part, dict):
            inline = part.get("inline_data") or part.get("inlineData")
        data = None
        if inline is not None:
            data = getattr(inline, "data", None)
            if data is None and isinstance(inline, dict):
                data = inline.get("data")
        if data is not None:
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                return base64.b64decode(data)
            # google.genai may expose memoryview / bytearray
            try:
                return bytes(data)
            except (TypeError, ValueError):
                pass  # fall through to the as_image() fallback below

        # Fallback (also reached when inline_data had no usable bytes):
        # part.as_image() → PIL → PNG bytes
        as_image = getattr(part, "as_image", None)
        if callable(as_image):
            try:
                from io import BytesIO

                img = as_image()
                buf = BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
            except Exception:  # noqa: BLE001 — try next part
                continue

    raise AppError("Gemini image API returned no image bytes")


class GeminiInfographicProvider:
    """Calls Gemini native image generation via google.genai Client (SDK-based)."""

    provider_name = "gemini_infographic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        provider_config: dict[str, Any] | None = None,
        pricing_config: dict[str, Any] | None = None,
        client: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = (api_key if api_key is not None else settings.GEMINI_API_KEY).strip()
        self._cfg = provider_config if provider_config is not None else _load_yaml(_PROVIDER_CFG)
        self._defaults = self._cfg.get("defaults") or {}
        self._model = model
        self._pricing = pricing_config if pricing_config is not None else _load_yaml(_PRICING_CFG)
        self._client = client
        self._timeout = float(self._cfg.get("timeout_seconds") or 120)

    def _require_key(self) -> None:
        if not self._api_key and self._client is None:
            raise AppError("GEMINI_API_KEY is required for the gemini_infographic pipeline")

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        self._require_key()
        try:
            from google import genai
        except ImportError as exc:
            raise AppError(
                "google-genai package is required for the gemini_infographic pipeline "
                "(pip install google-genai)"
            ) from exc
        return genai.Client(api_key=self._api_key)

    def _build_contents(self, request: ImageGenerationRequest) -> list[Any]:
        """Build multimodal contents: prompt text + optional reference images."""
        from google.genai import types

        params = dict(request.parameters or {})
        meta = dict(request.metadata or {})
        parts: list[Any] = [types.Part.from_text(text=request.prompt or "")]

        refs = params.get("reference_images") or meta.get("reference_images") or []
        ref_cfg = self._cfg.get("reference_images") or {}
        max_count = int(ref_cfg.get("max_count") or 3)
        max_bytes = int(ref_cfg.get("max_bytes_each") or 7_340_032)

        for ref in list(refs)[:max_count]:
            if not isinstance(ref, dict):
                continue
            raw = ref.get("bytes") or ref.get("data")
            mime = str(ref.get("mime_type") or ref.get("mime") or "image/png")
            if raw is None:
                continue
            if isinstance(raw, str):
                try:
                    raw = base64.b64decode(raw)
                except Exception:  # noqa: BLE001
                    continue
            if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
                continue
            if len(raw) > max_bytes:
                logger.warning(
                    "gemini_infographic_reference_skipped reason=too_large bytes=%s max=%s",
                    len(raw),
                    max_bytes,
                )
                continue
            parts.append(types.Part.from_bytes(data=bytes(raw), mime_type=mime))

        return parts

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_key()
        started = time.perf_counter()
        params = dict(request.parameters or {})
        meta_in = dict(request.metadata or {})
        quality_tier = str(
            params.get("quality_tier")
            or params.get("quality")
            or self._defaults.get("quality_tier")
            or "standard"
        ).lower()
        if quality_tier in {"high", "pro"}:
            quality_tier = "premium"
        if quality_tier in {"medium", "low", "flash"}:
            quality_tier = "standard"

        model = resolve_gemini_model(
            quality_tier=quality_tier,
            explicit_model=str(params.get("model") or self._model or "") or None,
            cfg=self._cfg,
        )
        aspect = str(
            params.get("aspect_ratio")
            or meta_in.get("aspect_ratio")
            or map_aspect_ratio(request.width, request.height, self._cfg)
        )
        image_size_map = self._cfg.get("image_size_by_tier") or {}
        image_size = params.get("image_size")
        if image_size is None:
            image_size = image_size_map.get(quality_tier)

        from google.genai import types

        client = self._get_client()
        contents = self._build_contents(request)
        modalities = list(
            params.get("response_modalities")
            or self._defaults.get("response_modalities")
            or ["IMAGE", "TEXT"]
        )

        image_config_kwargs: dict[str, Any] = {"aspect_ratio": aspect}
        if image_size:
            image_config_kwargs["image_size"] = str(image_size)

        config = types.GenerateContentConfig(
            response_modalities=modalities,
            image_config=types.ImageConfig(**image_config_kwargs),
        )

        prompt = request.prompt or ""
        neg = (request.negative_prompt or "").strip()
        if neg and "strictly avoid" not in prompt.lower():
            # Fold negative into last text part if we only had text — rebuild with ban line
            contents = self._build_contents(
                ImageGenerationRequest(
                    prompt=f"{prompt.rstrip()}\n\nStrictly avoid: {neg}",
                    width=request.width,
                    height=request.height,
                    style=request.style,
                    negative_prompt="",
                    parameters=request.parameters,
                    metadata=request.metadata,
                )
            )

        try:
            aio = getattr(client, "aio", None)
            if aio is not None and hasattr(aio, "models"):
                response = await asyncio.wait_for(
                    aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=self._timeout,
                )
            else:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=self._timeout,
                )
        except TimeoutError as exc:
            raise AppError(f"Gemini image generation timed out after {self._timeout}s") from exc
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 — normalize vendor errors
            raise AppError(f"Gemini image API error: {exc}") from exc

        image_bytes = _extract_inline_image_bytes(response)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = estimate_gemini_image_cost(model, quality_tier, pricing=self._pricing)

        metadata: dict[str, Any] = {
            "style": request.style,
            "requested_size": f"{request.width}x{request.height}",
            "aspect_ratio": aspect,
            "quality_tier": quality_tier,
            "image_byte_length": len(image_bytes),
            "image_size": image_size,
        }
        correlation_id = meta_in.get("correlation_id") or meta_in.get("request_id")
        if correlation_id:
            metadata["correlation_id"] = correlation_id

        logger.info(
            "Gemini infographic image generated: model=%s aspect=%s tier=%s latency_ms=%d bytes=%d",
            model,
            aspect,
            quality_tier,
            latency_ms,
            len(image_bytes),
        )

        return ImageGenerationResult(
            image_bytes=image_bytes,
            width=request.width,
            height=request.height,
            provider="gemini",
            model=model,
            latency_ms=latency_ms,
            cost_estimate=cost,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
            metadata=metadata,
        )
