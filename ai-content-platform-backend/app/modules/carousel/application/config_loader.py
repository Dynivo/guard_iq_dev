"""Config loading for carousel module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[4]
CAROUSEL_ROOT = _ROOT / "configs" / "carousel"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def load_carousel(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    return load_yaml((config_dir or CAROUSEL_ROOT) / name)
