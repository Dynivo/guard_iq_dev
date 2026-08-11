"""Review workflow templates — Marketing / Engineering / Compliance / etc."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.modules.review.domain.models import ReviewPriority, ReviewSession

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "review" / "workflow_templates"

TEMPLATE_IDS = (
    "marketing",
    "engineering",
    "compliance",
    "cybersecurity",
    "healthcare",
    "finance",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=16)
def load_workflow_template(template_id: str, config_dir: str | None = None) -> dict[str, Any]:
    root = Path(config_dir) if config_dir else _DEFAULT_DIR
    tid = template_id.strip().lower()
    return _load_yaml(root / f"{tid}.yaml")


def clear_workflow_template_cache() -> None:
    load_workflow_template.cache_clear()


class ReviewWorkflowTemplateService:
    def __init__(self, config_dir: str | None = None) -> None:
        # Directory containing *.yaml templates
        if config_dir:
            p = Path(config_dir)
            self._dir = str(p / "workflow_templates") if (p / "workflow_templates").is_dir() else str(p)
        else:
            self._dir = str(_DEFAULT_DIR)

    def list_ids(self) -> list[str]:
        root = Path(self._dir)
        if not root.is_dir():
            return list(TEMPLATE_IDS)
        found = sorted(p.stem for p in root.glob("*.yaml"))
        return found or list(TEMPLATE_IDS)

    def get(self, template_id: str) -> dict[str, Any]:
        return load_workflow_template(template_id, self._dir)

    def apply(self, session: ReviewSession, template_id: str) -> ReviewSession:
        tpl = self.get(template_id)
        if not tpl:
            session.metadata = {**session.metadata, "template_id": template_id}
            return session
        body = tpl.get("template") or tpl
        priority = body.get("priority")
        if priority:
            session.priority = ReviewPriority(str(priority))
        meta = dict(session.metadata)
        meta["template_id"] = template_id
        if body.get("topic") and "topic" not in meta:
            meta["topic"] = body["topic"]
        if body.get("risk") and "risk" not in meta:
            meta["risk"] = body["risk"]
        if body.get("required_reviewers") is not None:
            meta["template_required_reviewers"] = int(body["required_reviewers"])
        if body.get("quorum") is not None:
            meta["template_quorum"] = int(body["quorum"])
        cats = body.get("reason_code_categories") or body.get("categories") or []
        if cats:
            meta["suggested_categories"] = list(cats)
        specs = body.get("specializations") or []
        if specs:
            meta["specializations"] = list(specs)
        session.metadata = meta
        return session
