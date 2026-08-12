"""Resolve ImageProvider from configuration."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.image_generation.comfyui_adapter import ComfyUIAdapter
from app.infrastructure.image_generation.mock_generator import MockImageGenerator
from app.infrastructure.image_generation.workflow_registry import FileComfyWorkflowRegistry
from app.modules.image.domain.ports import ImageProvider

logger = get_logger(__name__)


def get_image_generator(provider_name: str | None = None) -> ImageProvider:
    settings = get_settings()
    name = (provider_name or settings.IMAGE_PROVIDER).lower().strip()
    if name == "comfyui":
        return ComfyUIAdapter(registry=FileComfyWorkflowRegistry())
    if name == "openai":
        from app.infrastructure.image_generation.openai_provider import OpenAIImageProvider

        return OpenAIImageProvider()
    if name == "gemini":
        from app.infrastructure.image_generation.gemini_provider import GeminiImageProvider

        return GeminiImageProvider()
    if name and name not in {"mock", ""}:
        logger.warning("Unknown IMAGE_PROVIDER=%s; falling back to mock", name)
    return MockImageGenerator()


get_image_provider = get_image_generator
