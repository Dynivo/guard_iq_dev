"""LearningProcessor — map LearningEvent → knowledge artifacts (no prompt rewrite)."""

from __future__ import annotations

from app.modules.learning.application.config_loader import load_learning_config
from app.modules.learning.domain.models import (
    KnowledgeArtifact,
    KnowledgeLifecycle,
    LearningArtifactKind,
    LearningEvent,
)


class LearningProcessor:
    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_learning_config(config_dir)

    def _confidence_default(self, kind: str, spec: dict) -> float:
        if spec.get("confidence") is not None:
            return float(spec["confidence"])
        process_cfg = (self._config.get("process") or {}).get("process") or {}
        defaults = process_cfg.get("confidence_defaults") or {}
        return float(defaults.get(kind) or 0.5)

    def _candidate(
        self,
        *,
        kind: LearningArtifactKind,
        organization_id,
        body: str,
        category: str,
        metadata: dict,
        confidence: float,
        source_learning_event_id,
    ) -> KnowledgeArtifact:
        return KnowledgeArtifact(
            kind=kind,
            organization_id=organization_id,
            body=body,
            category=category,
            metadata=metadata,
            confidence=confidence,
            approval_count=0,
            usage_count=0,
            success_rate=0.0,
            created_from_review=True,
            last_used=None,
            lifecycle=KnowledgeLifecycle.CANDIDATE,
            source_learning_event_id=source_learning_event_id,
        )

    def process(self, learning_event: LearningEvent) -> list[KnowledgeArtifact]:
        process_cfg = (self._config.get("process") or {}).get("process") or {}
        mapping = process_cfg.get(learning_event.source_event_type) or {}
        specs = mapping.get("artifacts") or []
        payload = learning_event.payload
        artifacts: list[KnowledgeArtifact] = []

        for spec in specs:
            kind = LearningArtifactKind(str(spec.get("kind")))
            conf = self._confidence_default(str(kind), spec)
            if kind == LearningArtifactKind.EXAMPLE:
                text = (payload.get("text") or "").strip()
                if not text:
                    continue
                artifacts.append(
                    self._candidate(
                        kind=kind,
                        organization_id=learning_event.organization_id,
                        body=text,
                        category=str(payload.get("content_type") or "linkedin_post"),
                        metadata={
                            "hook": payload.get("hook"),
                            "draft_id": payload.get("draft_id"),
                            "tags": list(spec.get("tags") or ["approved"]),
                            "weight": float(spec.get("weight") or 1.0),
                            "content_type": payload.get("content_type"),
                        },
                        confidence=conf,
                        source_learning_event_id=learning_event.id,
                    )
                )
            elif kind == LearningArtifactKind.NEGATIVE_RULE:
                reason = (payload.get("reason") or "").strip() or "Rejected without detail"
                category = str(payload.get("category") or "general")
                artifacts.append(
                    self._candidate(
                        kind=kind,
                        organization_id=learning_event.organization_id,
                        body=reason,
                        category=category,
                        metadata={
                            "priority": int(spec.get("priority") or 10),
                            "reason_codes": list(payload.get("reason_codes") or []),
                            "feedback_event_id": payload.get("feedback_event_id"),
                        },
                        confidence=conf,
                        source_learning_event_id=learning_event.id,
                    )
                )
            elif kind == LearningArtifactKind.WRITING_PREFERENCE:
                original = payload.get("original_text") or ""
                edited = payload.get("edited_text") or ""
                preference = "Prefer edited phrasing over first draft when similar topics recur."
                if len(edited) < len(original) * 0.8:
                    preference = "Prefer shorter, tighter posts."
                elif len(edited) > len(original) * 1.2:
                    preference = "Prefer more explanatory detail in posts."
                artifacts.append(
                    self._candidate(
                        kind=kind,
                        organization_id=learning_event.organization_id,
                        body=preference,
                        category="style",
                        metadata={
                            "source_type": "edit_diff",
                            "original_len": len(original),
                            "edited_len": len(edited),
                        },
                        confidence=conf,
                        source_learning_event_id=learning_event.id,
                    )
                )
            elif kind == LearningArtifactKind.KNOWLEDGE_SIGNAL:
                original = payload.get("original_text") or ""
                edited = payload.get("edited_text") or ""
                ratio = abs(len(edited) - len(original)) / max(len(original), 1)
                artifacts.append(
                    self._candidate(
                        kind=kind,
                        organization_id=learning_event.organization_id,
                        body=f"edit_ratio={round(ratio, 4)}",
                        category="signal",
                        metadata={
                            "signal": spec.get("signal") or "edit_diff",
                            "edit_ratio": round(ratio, 4),
                        },
                        confidence=conf,
                        source_learning_event_id=learning_event.id,
                    )
                )
            elif kind == LearningArtifactKind.BRAND_PREFERENCE:
                artifacts.append(
                    self._candidate(
                        kind=kind,
                        organization_id=learning_event.organization_id,
                        body=str(payload.get("reason") or "brand preference signal"),
                        category="brand",
                        metadata={"reason_codes": list(payload.get("reason_codes") or [])},
                        confidence=conf,
                        source_learning_event_id=learning_event.id,
                    )
                )
            elif kind == LearningArtifactKind.RECOMMENDATION:
                artifacts.append(
                    self._candidate(
                        kind=kind,
                        organization_id=learning_event.organization_id,
                        body=str(spec.get("body") or "Review learning recommendation"),
                        category="recommendation",
                        metadata=dict(spec.get("metadata") or {}),
                        confidence=conf,
                        source_learning_event_id=learning_event.id,
                    )
                )

        rec_cfg = process_cfg.get("recommendations") or {}
        if (
            rec_cfg.get("enabled")
            and learning_event.source_event_type == "DraftEdited"
            and artifacts
        ):
            min_ratio = float(rec_cfg.get("min_edit_ratio_for_signal") or 0.15)
            signals = [
                a
                for a in artifacts
                if a.kind == LearningArtifactKind.KNOWLEDGE_SIGNAL
                and float((a.metadata or {}).get("edit_ratio") or 0) >= min_ratio
            ]
            if signals:
                artifacts.append(
                    self._candidate(
                        kind=LearningArtifactKind.RECOMMENDATION,
                        organization_id=learning_event.organization_id,
                        body="Consider tightening first-draft generation toward edited length.",
                        category="recommendation",
                        metadata={"from_signal": signals[0].body},
                        confidence=self._confidence_default("recommendation", {}),
                        source_learning_event_id=learning_event.id,
                    )
                )

        return artifacts
