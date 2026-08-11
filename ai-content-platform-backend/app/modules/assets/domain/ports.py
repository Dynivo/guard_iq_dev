"""Asset Management ports — storage and delivery (M2).

Full Asset Management (versioning UI, approvals, lifecycle) lands in M9.
M2 introduces StorageProvider + DeliveryStrategy so image/carousel write paths
and authenticated delivery no longer depend on a vendor-specific object store SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    """Result of writing bytes to a StorageProvider."""

    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class DeliveryDescriptor:
    """How a client should obtain an asset version's bytes."""

    strategy: str
    url: str
    content_type: str | None = None
    expires_at: datetime | None = None
    headers: dict[str, str] = field(default_factory=dict)


class StorageProvider(Protocol):
    """Replaceable object storage — Local (dev) or private S3 (production)."""

    def put_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject: ...

    def get_bytes(self, storage_key: str) -> bytes: ...

    def exists(self, storage_key: str) -> bool: ...

    def delete(self, storage_key: str) -> None: ...


class DeliveryStrategy(Protocol):
    """Resolve how the frontend obtains asset bytes (stream, short-lived URL, CDN, …)."""

    @property
    def name(self) -> str: ...

    def resolve(
        self,
        storage_key: str,
        *,
        content_type: str | None = None,
    ) -> DeliveryDescriptor: ...
