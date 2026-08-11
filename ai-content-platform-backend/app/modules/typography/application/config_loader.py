"""Config loading for typography / brand modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[4]
TYPO_ROOT = _ROOT / "configs" / "typography"
BRAND_ROOT = _ROOT / "configs" / "brand"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def load_typography(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    return load_yaml((config_dir or TYPO_ROOT) / name)


def load_brand(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    return load_yaml((config_dir or BRAND_ROOT) / name)
