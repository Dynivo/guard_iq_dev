"""Ensure MinIO is fully removed from application code and dependencies."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
REQ = ROOT / "requirements.txt"


def test_no_minio_imports_in_app() -> None:
    offenders: list[str] = []
    patterns = (
        "from minio",
        "import minio",
        "infrastructure.minio",
        "ObjectStorage",
        "MINIO_",
    )
    for path in APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(p in text for p in patterns):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"MinIO remnants in app code: {offenders}"


def test_requirements_has_no_minio() -> None:
    text = REQ.read_text(encoding="utf-8").lower()
    assert "minio" not in text


def test_minio_package_directory_removed() -> None:
    assert not (APP / "infrastructure" / "minio").exists()


def test_minio_not_importable_as_app_module() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("app.infrastructure.minio.storage")
