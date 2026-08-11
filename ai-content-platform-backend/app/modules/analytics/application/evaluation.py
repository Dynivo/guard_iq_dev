"""Evaluation Engine — deterministic, reproducible scores (no LLM)."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.modules.analytics.application.config_loader import load_analytics_config
from app.modules.analytics.application.store import InMemoryObservabilityStore
from app.modules.analytics.domain.models import EvaluationResult


class EvaluationEngine:
    def __init__(
        self,
        store: InMemoryObservabilityStore,
        config_dir: str | None = None,
    ) -> None:
        self._store = store
        self._config = load_analytics_config(config_dir)

    def _cfg(self) -> dict[str, Any]:
        return (self._config.get("evaluation") or {}).get("evaluation") or {}

    @staticmethod
    def fingerprint(inputs: dict[str, Any]) -> str:
        raw = json.dumps(inputs, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def evaluate(
        self,
        *,
        organization_id: uuid.UUID,
        correlation_id: str,
        subject_type: str,
        subject_id: str,
        inputs: dict[str, Any],
    ) -> EvaluationResult:
        cfg = self._cfg()
        weights = cfg.get("weights") or {}
        thresholds = cfg.get("thresholds") or {}
        budget = float(cfg.get("latency_budget_ms") or 3000)

        approval_rate = float(inputs.get("approval_rate") or 0.0)
        edit_distance = float(inputs.get("edit_distance") or 0.0)
        latency_ms = float(inputs.get("latency_ms") or 0.0)
        learning_growth = float(inputs.get("learning_growth") or 0.0)
        visual_quality = float(inputs.get("visual_quality") or 0.5)
        typography_quality = float(inputs.get("typography_quality") or 0.5)
        carousel_quality = float(inputs.get("carousel_quality") or 0.5)

        edit_inv = max(0.0, 1.0 - (edit_distance / max(float(thresholds.get("high_edit_distance") or 40), 1)))
        latency_score = max(0.0, 1.0 - (latency_ms / max(budget, 1)))

        scores = {
            "approval_rate": round(approval_rate, 4),
            "edit_distance_inverse": round(edit_inv, 4),
            "latency_budget": round(latency_score, 4),
            "learning_growth": round(min(1.0, learning_growth), 4),
            "visual_quality": round(visual_quality, 4),
            "typography_quality": round(typography_quality, 4),
            "carousel_quality": round(carousel_quality, 4),
        }
        overall = 0.0
        weight_sum = 0.0
        for key, score in scores.items():
            w = float(weights.get(key) or 0.0)
            overall += w * score
            weight_sum += w
        if weight_sum > 0:
            overall = overall / weight_sum

        signals: list[str] = []
        if edit_distance >= float(thresholds.get("high_edit_distance") or 40):
            signals.append("high_edit_distance")
        if approval_rate < float(thresholds.get("low_approval_rate") or 0.4) and inputs.get(
            "approval_rate"
        ) is not None:
            signals.append("low_approval_rate")
        if latency_ms >= float(thresholds.get("high_latency_ms") or 5000):
            signals.append("high_latency")

        result = EvaluationResult(
            evaluation_id=str(uuid.uuid4()),
            correlation_id=correlation_id,
            organization_id=organization_id,
            subject_type=subject_type,
            subject_id=subject_id,
            scores=scores,
            overall=round(overall, 4),
            signals=tuple(signals),
            inputs_fingerprint=self.fingerprint(inputs),
            metadata={"inputs": dict(inputs)},
        )
        return result

    async def evaluate_and_store(self, **kwargs: Any) -> EvaluationResult:
        result = self.evaluate(**kwargs)
        await self._store.store_evaluation(result)
        return result
