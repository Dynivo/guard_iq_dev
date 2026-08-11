"""Load configs/consensus/*.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[4] / "configs" / "consensus"


def _load(name: str) -> dict[str, Any]:
    path = _ROOT / name
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=1)
def load_consensus_config() -> dict[str, Any]:
    return {
        "providers": _load("providers.yaml"),
        "weights": _load("weights.yaml"),
        "evaluation": _load("evaluation.yaml"),
        "merge": _load("merge.yaml"),
        "policies": _load("policies.yaml"),
        "judge": _load("judge.yaml"),
        "cost": _load("cost.yaml"),
    }


def reload_consensus_config() -> dict[str, Any]:
    load_consensus_config.cache_clear()
    return load_consensus_config()
