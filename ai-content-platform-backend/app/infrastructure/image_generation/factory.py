"""Resolve ImageProvider from configuration."""

from __future__ import annotations

from app.core.config import get_settings
from app.infrastructure.image_generation.comfyui_adapter import ComfyUIAdapter
from app.infrastructure.image_generation.workflow_registry import FileComfyWorkflowRegistry
from app.modules.image.domain.ports import ImageProvider

def get_image_generator(provider_name: str | None = None) -> ImageProvider:
    settings = get_settings()
    name = (provider_name or settings.IMAGE_PROVIDER or "gemini").lower().strip()
    if name == "comfyui":
        return ComfyUIAdapter(registry=FileComfyWorkflowRegistry())
    if name == "openai":
        from app.infrastructure.image_generation.openai_provider import OpenAIImageProvider

        return OpenAIImageProvider()
    if name == "gemini":
        from app.infrastructure.image_generation.gemini_provider import GeminiImageProvider

        return GeminiImageProvider()
    if name == "gemini_infographic":
        from app.infrastructure.image_generation.gemini_infographic_provider import (
            GeminiInfographicProvider,
        )

        return GeminiInfographicProvider()
    raise ValueError(
        f"Unknown image provider '{name}'. Configure openai, gemini, "
        "gemini_infographic, or comfyui."
    )


get_image_provider = get_image_generator
