"""Consensus Engine domain models (M17 / ADR 0058)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ConsensusRequest:
    prompt: str
    capability: str = "writing"
    system_message: str = ""
    organization_id: uuid.UUID | None = None
    correlation_id: str = ""
    response_format: str = "json"
    prompt_version: str = ""
    policy_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_prompt_fields(
        cls,
        *,
        prompt: str,
        capability: str = "writing",
        system_message: str = "",
        organization_id: uuid.UUID | None = None,
        correlation_id: str = "",
        response_format: str = "json",
        prompt_version: str = "",
        policy_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ConsensusRequest:
        return cls(
            prompt=prompt,
            capability=capability,
            system_message=system_message,
            organization_id=organization_id,
            correlation_id=correlation_id,
            response_format=response_format,
            prompt_version=prompt_version,
            policy_id=policy_id,
            metadata=dict(metadata or {}),
        )


@dataclass(slots=True)
class CandidateResponse:
    candidate_id: str
    provider: str
    model: str
    text: str
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_estimate: float = 0.0
    success: bool = True
    error: str = ""
    sections: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    anonymous_id: str = ""


@dataclass(slots=True)
class EvaluationScore:
    candidate_id: str
    scores: dict[str, float] = field(default_factory=dict)
    composite: float = 0.0
    passed: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JudgeDecision:
    rankings: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    model: str = ""
    latency_ms: int = 0
    anonymized: bool = True


@dataclass(slots=True)
class ConsensusMetrics:
    agreement: float = 0.0
    consensus_score: float = 0.0
    candidate_count: int = 0
    successful_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MergeDecision:
    merged_text: str
    merged_sections: dict[str, Any] = field(default_factory=dict)
    section_sources: dict[str, str] = field(default_factory=dict)  # section -> candidate_id
    strategy: str = "section_best"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CritiqueReport:
    issues: list[dict[str, Any]] = field(default_factory=list)
    affected_sections: list[str] = field(default_factory=list)
    severity: str = "low"
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    model: str = ""


@dataclass(slots=True)
class ProviderWeight:
    provider: str
    reliability: float = 0.7
    latency: float = 0.7
    cost: float = 0.7
    historical_success: float = 0.5
    domain_score: float = 0.5
    brand_score: float = 0.5
    writing_score: float = 0.5
    research_score: float = 0.5
    image_prompt_score: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def composite(self) -> float:
        vals = (
            self.reliability,
            self.writing_score,
            self.historical_success,
            self.domain_score,
            self.brand_score,
        )
        return sum(vals) / len(vals)


@dataclass(slots=True)
class ConsensusRun:
    run_id: str
    organization_id: uuid.UUID | None
    correlation_id: str
    capability: str
    policy_id: str
    status: str = "completed"
    candidates: list[CandidateResponse] = field(default_factory=list)
    evaluations: list[EvaluationScore] = field(default_factory=list)
    judge: JudgeDecision | None = None
    consensus: ConsensusMetrics | None = None
    merge: MergeDecision | None = None
    critique: CritiqueReport | None = None
    final_text: str = ""
    total_cost: float = 0.0
    total_latency_ms: int = 0
    panel: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_report(self) -> dict[str, Any]:
        """Developer-facing report — never includes system prompts or CoT."""
        return {
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "capability": self.capability,
            "policy_id": self.policy_id,
            "status": self.status,
            "panel": list(self.panel),
            "candidate_count": len(self.candidates),
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "provider": c.provider,
                    "model": c.model,
                    "success": c.success,
                    "error": c.error or None,
                    "latency_ms": c.latency_ms,
                    "tokens_in": c.tokens_in,
                    "tokens_out": c.tokens_out,
                    "cost_estimate": c.cost_estimate,
                    "confidence": c.confidence,
                    "sections": list((c.sections or {}).keys()),
                }
                for c in self.candidates
            ],
            "failed_providers": list(
                (self.metadata or {}).get("failed_providers") or []
            ),
            "partial_success": bool((self.metadata or {}).get("partial_success")),
            "evaluations": [
                {
                    "candidate_id": e.candidate_id,
                    "composite": e.composite,
                    "passed": e.passed,
                    "scores": dict(e.scores),
                }
                for e in self.evaluations
            ],
            "judge": {
                "confidence": self.judge.confidence if self.judge else 0.0,
                "rankings": list(self.judge.rankings) if self.judge else [],
                "provider": self.judge.provider if self.judge else "",
            }
            if self.judge
            else None,
            "consensus": {
                "agreement": self.consensus.agreement if self.consensus else 0.0,
                "consensus_score": self.consensus.consensus_score if self.consensus else 0.0,
                "successful_count": self.consensus.successful_count if self.consensus else 0,
            }
            if self.consensus
            else None,
            "merge": {
                "section_sources": dict(self.merge.section_sources) if self.merge else {},
                "strategy": self.merge.strategy if self.merge else "",
                "sections": list((self.merge.merged_sections or {}).keys()) if self.merge else [],
            }
            if self.merge
            else None,
            "critique": {
                "severity": self.critique.severity if self.critique else "",
                "affected_sections": list(self.critique.affected_sections) if self.critique else [],
                "issue_count": len(self.critique.issues) if self.critique else 0,
            }
            if self.critique
            else None,
            "cost_report": {"total_cost": self.total_cost},
            "latency_report": {"total_latency_ms": self.total_latency_ms},
            "confidence_report": {
                "judge": self.judge.confidence if self.judge else 0.0,
                "consensus": self.consensus.consensus_score if self.consensus else 0.0,
            },
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ConsensusResult:
    success: bool
    final_text: str
    run: ConsensusRun
    provider: str = "consensus"
    model: str = "multi"
    error: str = ""
