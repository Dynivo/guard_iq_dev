"""Knowledge lifecycle — candidate → verified → approved → deprecated → archived."""

from __future__ import annotations

from typing import Any

from app.modules.learning.application.config_loader import load_learning_config
from app.modules.learning.domain.models import KnowledgeLifecycle
from app.shared.result import Result, fail, ok


_DEFAULT_TRANSITIONS: dict[str, list[str]] = {
    "candidate": ["verified", "archived"],
    "verified": ["approved", "deprecated", "archived"],
    "approved": ["deprecated", "archived"],
    "deprecated": ["archived", "approved"],
    "archived": [],
}


class KnowledgeLifecycleService:
    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_learning_config(config_dir)

    def _transitions(self) -> dict[str, list[str]]:
        life = (self._config.get("lifecycle") or {}).get("lifecycle") or {}
        raw = life.get("transitions") or _DEFAULT_TRANSITIONS
        return {str(k): [str(x) for x in v] for k, v in raw.items()}

    def is_consumable(self, lifecycle: KnowledgeLifecycle | str) -> bool:
        return str(lifecycle) == KnowledgeLifecycle.APPROVED

    def is_active_flag(self, lifecycle: KnowledgeLifecycle | str) -> bool:
        return self.is_consumable(lifecycle)

    def can_transition(
        self, current: KnowledgeLifecycle | str, target: KnowledgeLifecycle | str
    ) -> bool:
        allowed = self._transitions().get(str(current)) or []
        return str(target) in allowed

    def transition(
        self, current: KnowledgeLifecycle | str, target: KnowledgeLifecycle | str
    ) -> Result[dict[str, Any]]:
        cur = KnowledgeLifecycle(str(current))
        tgt = KnowledgeLifecycle(str(target))
        if not self.can_transition(cur, tgt):
            return fail("INVALID_LIFECYCLE", f"cannot transition {cur} → {tgt}")
        return ok(
            {
                "lifecycle": str(tgt),
                "is_active": self.is_active_flag(tgt),
                "previous": str(cur),
            }
        )
