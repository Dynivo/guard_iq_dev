"""Private AWS S3 StorageProvider."""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.modules.assets.domain.ports import StoredObject

logger = get_logger(__name__)


class S3StorageProvider:
    """Store objects in a private S3 bucket. Never exposes public bucket ACLs."""

    provider_name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        endpoint_url: str | None = None,
        prefix: str = "",
    ) -> None:
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "boto3 is required when STORAGE_PROVIDER=s3; pip install boto3"
            ) from exc

        self._bucket = bucket
        self._prefix = prefix.strip("/")
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": region,
            "config": Config(signature_version="s3v4"),
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self._client = boto3.client(**kwargs)

    def put_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        key = self._full_key(storage_key)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredObject(
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def get_bytes(self, storage_key: str) -> bytes:
        from botocore.exceptions import ClientError

        key = self._full_key(storage_key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404", "NotFound", "NoSuchBucket"}:
                raise NotFoundError("Media", storage_key) from exc
            raise
        return response["Body"].read()

    def exists(self, storage_key: str) -> bool:
        from botocore.exceptions import ClientError

        key = self._full_key(storage_key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, storage_key: str) -> None:
        key = self._full_key(storage_key)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def _full_key(self, storage_key: str) -> str:
        if ".." in storage_key.split("/"):
            raise ValueError("Invalid storage key")
        if self._prefix:
            return f"{self._prefix}/{storage_key}"
        return storage_key
