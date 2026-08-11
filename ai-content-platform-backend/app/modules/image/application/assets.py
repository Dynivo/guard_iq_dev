"""Storage-backed image asset persistence (local filesystem)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.assets.domain.ports import StorageProvider
from app.modules.image.domain.models import ImageArtifactRole, ImageAssetRecord, OptimizedImageBundle

logger = get_logger(__name__)


class StorageWriteError(AppError):
    status_code = 500
    error_code = "IMAGE_STORAGE_WRITE_FAILED"


def storage_backend_name(storage: StorageProvider | None = None) -> str:
    """Human-readable backend: local | memory."""
    if storage is None:
        return "memory"
    name = getattr(storage, "provider_name", None)
    if name:
        return str(name)
    settings = get_settings()
    return (settings.STORAGE_PROVIDER or "local").lower().strip()


def persist_png(
    storage: StorageProvider,
    storage_key: str,
    data: bytes,
    *,
    verify: bool | None = None,
) -> dict[str, Any]:
    """Write PNG bytes through StorageProvider; optionally verify the object exists."""
    if not data:
        raise StorageWriteError(f"Refusing to store empty image at {storage_key}")
    stored = storage.put_bytes(storage_key, data, "image/png")
    backend = storage_backend_name(storage)
    should_verify = bool(verify)
    if should_verify and not storage.exists(storage_key):
        raise StorageWriteError(
            f"Image write to {backend} reported success but object missing: {storage_key}"
        )
    logger.info(
        "image_asset_stored backend=%s key=%s bytes=%d sha256=%s",
        backend,
        storage_key,
        len(data),
        stored.sha256[:16],
    )
    return {
        "storage_backend": backend,
        "storage_key": storage_key,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
    }


class MemoryImageAssetStore:
    """Persists original / optimized / thumbnail via StorageProvider (local disk).

    Keeps an in-process blob cache for the same request (canonical re-key in VisualWorkflow).
    Name retained for backwards compatibility with tests/handlers.
    """

    def __init__(
        self,
        storage: StorageProvider | None = None,
        *,
        require_storage: bool = False,
    ) -> None:
        if require_storage and storage is None:
            raise StorageWriteError(
                "ImageAssetStore requires a StorageProvider "
                "(set STORAGE_PROVIDER=local)"
            )
        self._storage = storage
        self._assets: list[ImageAssetRecord] = []
        self.blobs: dict[str, bytes] = {}

    @property
    def storage(self) -> StorageProvider | None:
        return self._storage

    async def store(
        self,
        *,
        organization_id: str,
        job_id: str,
        draft_id: str,
        bundle: OptimizedImageBundle,
        metadata: dict[str, Any],
    ) -> tuple[ImageAssetRecord, ...]:
        records: list[ImageAssetRecord] = []
        mapping = (
            (ImageArtifactRole.ORIGINAL.value, bundle.original_bytes, bundle.width, bundle.height),
            (ImageArtifactRole.OPTIMIZED.value, bundle.optimized_bytes, bundle.width, bundle.height),
            (
                ImageArtifactRole.THUMBNAIL.value,
                bundle.thumbnail_bytes,
                bundle.thumb_width,
                bundle.thumb_height,
            ),
        )
        backend = storage_backend_name(self._storage)
        for role, data, w, h in mapping:
            key = f"{organization_id}/images/{job_id}/{role}.png"
            sha = hashlib.sha256(data).hexdigest()
            meta = {
                **metadata,
                "draft_id": draft_id,
                "storage_backend": backend,
                "role": role,
            }
            if self._storage is not None:
                written = persist_png(self._storage, key, data)
                meta.update(written)
            else:
                logger.warning(
                    "image_asset_memory_only key=%s — configure STORAGE_PROVIDER=local for durable store",
                    key,
                )
            self.blobs[key] = data
            rec = ImageAssetRecord(
                asset_id=str(uuid.uuid4()),
                job_id=job_id,
                role=role,
                object_key=key,
                width=w,
                height=h,
                sha256=sha,
                mime_type="image/png",
                metadata=meta,
            )
            records.append(rec)
            self._assets.append(rec)
        return tuple(records)
