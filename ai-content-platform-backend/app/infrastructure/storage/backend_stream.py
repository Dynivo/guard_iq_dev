"""Backend-stream DeliveryStrategy — authenticated FastAPI media route."""

from __future__ import annotations

from app.modules.assets.domain.ports import DeliveryDescriptor


class BackendStreamDeliveryStrategy:
    """Default M2/dev strategy: clients fetch via authenticated backend stream URL."""

    STRATEGY_NAME = "backend_stream"
    URL_PREFIX = "/api/v1/media/objects"

    @property
    def name(self) -> str:
        return self.STRATEGY_NAME

    def resolve(
        self,
        storage_key: str,
        *,
        content_type: str | None = None,
    ) -> DeliveryDescriptor:
        return DeliveryDescriptor(
            strategy=self.STRATEGY_NAME,
            url=f"{self.URL_PREFIX}/{storage_key}",
            content_type=content_type,
        )
