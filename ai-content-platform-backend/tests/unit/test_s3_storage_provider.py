"""Unit tests for S3StorageProvider with a mocked boto3 client."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError


def _client_error(code: str):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": "fail"}}, "GetObject")


pytest.importorskip("boto3")
from app.infrastructure.storage.s3 import S3StorageProvider  # noqa: E402


@patch("boto3.client")
def test_s3_put_and_get(mock_boto_client: MagicMock) -> None:
    client = MagicMock()
    mock_boto_client.return_value = client
    client.get_object.return_value = {"Body": BytesIO(b"hello-s3")}

    storage = S3StorageProvider(
        bucket="private-bucket",
        region="us-east-1",
        access_key_id="ak",
        secret_access_key="sk",
        prefix="prod",
    )
    stored = storage.put_bytes("org/x.png", b"hello-s3", "image/png")
    assert stored.storage_key == "org/x.png"
    assert stored.sha256
    client.put_object.assert_called_once()
    put_kwargs = client.put_object.call_args.kwargs
    assert put_kwargs["Bucket"] == "private-bucket"
    assert put_kwargs["Key"] == "prod/org/x.png"
    assert put_kwargs["ContentType"] == "image/png"

    assert storage.get_bytes("org/x.png") == b"hello-s3"
    client.get_object.assert_called_with(Bucket="private-bucket", Key="prod/org/x.png")


@patch("boto3.client")
def test_s3_get_missing(mock_boto_client: MagicMock) -> None:
    client = MagicMock()
    mock_boto_client.return_value = client
    client.get_object.side_effect = _client_error("NoSuchKey")

    storage = S3StorageProvider(bucket="b", region="us-east-1")
    with pytest.raises(NotFoundError):
        storage.get_bytes("missing.png")


@patch("boto3.client")
def test_s3_exists(mock_boto_client: MagicMock) -> None:
    client = MagicMock()
    mock_boto_client.return_value = client
    storage = S3StorageProvider(bucket="b", region="us-east-1")
    assert storage.exists("a.png") is True
    client.head_object.side_effect = _client_error("404")
    assert storage.exists("b.png") is False
