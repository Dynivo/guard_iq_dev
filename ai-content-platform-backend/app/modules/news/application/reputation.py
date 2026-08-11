"""Source reputation engine (+ feedback EMA hooks for source learning)."""

from __future__ import annotations

from dataclasses import replace

from app.modules.news.domain.models import (
    SourceDefinition,
    SourceFeedbackKind,
)


class DefaultSourceReputationEngine:
    def reputation(self, source: SourceDefinition) -> dict[str, float]:
        bias = 0.0  # reserved for future bias model
        historical_accuracy = source.reliability
        return {
            "authority": source.authority,
            "reliability": source.reliability,
            "trust": source.trust,
            "bias": bias,
            "historical_accuracy": historical_accuracy,
            "composite": round(
                (source.authority + source.reliability + source.trust) / 3.0, 4
            ),
        }

    def apply_feedback(
        self,
        source: SourceDefinition,
        kind: SourceFeedbackKind,
        *,
        weight: float = 1.0,
        alpha: float = 0.15,
    ) -> SourceDefinition:
        """Bounded EMA update — used by SourceLearningEngine."""
        delta = _delta_for(kind) * max(0.1, min(2.0, weight))
        authority = _clamp(source.authority + alpha * delta)
        reliability = _clamp(source.reliability + alpha * delta * 0.8)
        trust = _clamp(source.trust + alpha * delta * 0.9)
        return replace(
            source, authority=authority, reliability=reliability, trust=trust
        )


def _delta_for(kind: SourceFeedbackKind) -> float:
    if kind == SourceFeedbackKind.APPROVAL:
        return 1.0
    if kind == SourceFeedbackKind.REJECTION:
        return -1.0
    if kind == SourceFeedbackKind.USER_EDIT:
        return 0.25
    if kind == SourceFeedbackKind.ENGAGEMENT:
        return 0.5
    return 0.0


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)
