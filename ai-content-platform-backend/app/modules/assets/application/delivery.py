"""Thin Asset Delivery application helper (M2).

Resolves DeliveryDescriptor for a stored object. Full Asset Management arrives in M9.
"""

from __future__ import annotations

from app.infrastructure.storage.factory import get_delivery_strategy
from app.modules.assets.domain.ports import DeliveryDescriptor, DeliveryStrategy


class AssetDeliveryService:
    """Application facade over DeliveryStrategy."""

    def __init__(self, strategy: DeliveryStrategy | None = None) -> None:
        self._strategy = strategy or get_delivery_strategy()

    def resolve_url(
        self,
        storage_key: str,
        *,
        content_type: str | None = None,
    ) -> DeliveryDescriptor:
        return self._strategy.resolve(storage_key, content_type=content_type)
