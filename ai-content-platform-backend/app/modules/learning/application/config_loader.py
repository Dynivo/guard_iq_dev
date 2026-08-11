"""Load learning YAML configs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "learning"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


@lru_cache(maxsize=8)
def load_learning_config(config_dir: str | None = None) -> dict[str, Any]:
    root = Path(config_dir) if config_dir else _DEFAULT_DIR
    return {
        "capture": _load_yaml(root / "capture.yaml"),
        "process": _load_yaml(root / "process.yaml"),
        "store": _load_yaml(root / "store.yaml"),
        "lifecycle": _load_yaml(root / "lifecycle.yaml"),
    }


def clear_learning_config_cache() -> None:
    load_learning_config.cache_clear()
