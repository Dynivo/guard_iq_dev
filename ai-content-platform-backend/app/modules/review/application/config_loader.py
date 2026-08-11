"""Load review YAML configs (policies, reason codes, templates)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "review"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


@lru_cache(maxsize=8)
def load_review_config(config_dir: str | None = None) -> dict[str, Any]:
    root = Path(config_dir) if config_dir else _DEFAULT_DIR
    return {
        "policies": _load_yaml(root / "policies.yaml"),
        "reason_codes": _load_yaml(root / "reason_codes.yaml"),
        "templates": _load_yaml(root / "templates.yaml"),
        "reviewer_intelligence": _load_yaml(root / "reviewer_intelligence.yaml"),
    }


def clear_review_config_cache() -> None:
    load_review_config.cache_clear()
