"""Factories for StorageProvider and DeliveryStrategy from settings."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.infrastructure.storage.backend_stream import BackendStreamDeliveryStrategy
from app.infrastructure.storage.local import LocalStorageProvider
from app.modules.assets.domain.ports import DeliveryStrategy, StorageProvider


class StorageConfigError(AppError):
    status_code = 500
    error_code = "STORAGE_CONFIG_ERROR"


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    provider = settings.STORAGE_PROVIDER.lower().strip()
    if provider == "local":
        return LocalStorageProvider(root=settings.STORAGE_LOCAL_ROOT)
    if provider == "s3":
        from app.infrastructure.storage.s3 import S3StorageProvider

        if not settings.S3_BUCKET:
            raise StorageConfigError("S3_BUCKET is required when STORAGE_PROVIDER=s3")
        return S3StorageProvider(
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            access_key_id=settings.S3_ACCESS_KEY_ID or None,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            prefix=settings.S3_PREFIX,
        )
    raise StorageConfigError(
        f"Unsupported STORAGE_PROVIDER={settings.STORAGE_PROVIDER!r}; use local|s3"
    )


@lru_cache(maxsize=1)
def get_delivery_strategy() -> DeliveryStrategy:
    settings = get_settings()
    name = settings.DELIVERY_STRATEGY.lower().strip()
    if name == "backend_stream":
        return BackendStreamDeliveryStrategy()
    raise StorageConfigError(
        f"Unsupported DELIVERY_STRATEGY={settings.DELIVERY_STRATEGY!r}; "
        "only backend_stream is implemented in M2"
    )


def clear_storage_caches() -> None:
    """Reset cached providers (tests / settings reload)."""
    get_storage_provider.cache_clear()
    get_delivery_strategy.cache_clear()
