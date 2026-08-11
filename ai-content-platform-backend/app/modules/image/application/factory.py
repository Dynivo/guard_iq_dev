"""Factory for Visual Intelligence Engine (memory / default provider)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.image_generation.factory import get_image_provider
from app.modules.image.application.assets import MemoryImageAssetStore
from app.modules.image.application.engine import DefaultVisualIntelligenceEngine
from app.modules.image.application.metrics import InMemoryImageMetrics
from app.modules.image.application.orchestrator import DefaultImageOrchestrator
from app.modules.image.domain.models import ImageGenerationRequest, ImageGenerationResult
from app.modules.image.domain.ports import ImageProvider

logger = get_logger(__name__)


class FallbackImageProvider:
    """Try primary provider; on failure fall back to mock so local demos still produce pixels."""

    def __init__(self, primary: ImageProvider, fallback: ImageProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return getattr(self._primary, "provider_name", "primary")

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        try:
            return await self._primary.generate(request)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Primary image provider failed (%s); falling back to mock: %s",
                self.provider_name,
                exc,
            )
            result = await self._fallback.generate(request)
            result.metadata = {
                **dict(result.metadata or {}),
                "fallback_from": self.provider_name,
                "fallback_error": str(exc)[:300],
            }
            return result


class VisualIntelligenceFactory:
    @staticmethod
    def create_memory(*, config_dir: Path | None = None) -> DefaultVisualIntelligenceEngine:
        """In-memory / mock path for unit tests (no durable object store required)."""
        provider = get_image_provider("mock")
        metrics = InMemoryImageMetrics()
        orch = DefaultImageOrchestrator(provider, config_dir=config_dir, metrics=metrics)
        return DefaultVisualIntelligenceEngine(
            orchestrator=orch,
            asset_store=MemoryImageAssetStore(),
            metrics=metrics,
            config_dir=config_dir,
        )

    @staticmethod
    def create(*, config_dir: Path | None = None) -> DefaultVisualIntelligenceEngine:
        """Production engine — pixels persist via STORAGE_PROVIDER (local or s3)."""
        from app.infrastructure.storage.factory import get_storage_provider

        settings = get_settings()
        primary = get_image_provider()
        name = (settings.IMAGE_PROVIDER or "mock").lower().strip()
        provider: ImageProvider = primary
        if name not in {"mock", ""}:
            provider = FallbackImageProvider(primary, get_image_provider("mock"))
        metrics = InMemoryImageMetrics()
        orch = DefaultImageOrchestrator(provider, config_dir=config_dir, metrics=metrics)
        storage = get_storage_provider()
        logger.info(
            "VisualIntelligenceFactory storage_backend=%s image_provider=%s",
            getattr(storage, "provider_name", settings.STORAGE_PROVIDER),
            name or "mock",
        )
        return DefaultVisualIntelligenceEngine(
            orchestrator=orch,
            asset_store=MemoryImageAssetStore(storage=storage, require_storage=True),
            metrics=metrics,
            config_dir=config_dir,
        )
