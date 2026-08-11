"""Shared config loading for image module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_ROOT = Path(__file__).resolve().parents[4] / "configs" / "image"


def load_yaml(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    path = (config_dir or CONFIG_ROOT) / name
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}
