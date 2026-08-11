"""Analytics / observability domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class TraceStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class CostCategory(StrEnum):
    PROVIDER = "provider"
    GENERATION = "generation"
    IMAGE = "image"
    RENDER = "render"
    STORAGE = "storage"
    WORKFLOW = "workflow"
    OTHER = "other"


@dataclass(slots=True)
class AITrace:
    request_id: str
    correlation_id: str
    organization_id: UUID
    workflow_id: str | None = None
    provider: str | None = None
    model: str | None = None
    capability: str | None = None
    user_id: str | None = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_hit: bool = False
    retry_count: int = 0
    status: TraceStatus = TraceStatus.UNKNOWN
    event_type: str | None = None
    cost_estimate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "organization_id": str(self.organization_id),
            "workflow_id": self.workflow_id,
            "provider": self.provider,
            "model": self.model,
            "capability": self.capability,
            "user_id": self.user_id,
            "latency_ms": self.latency_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cache_hit": self.cache_hit,
            "retry_count": self.retry_count,
            "status": str(self.status),
            "event_type": self.event_type,
            "cost_estimate": self.cost_estimate,
            "metadata": dict(self.metadata),
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
        }


@dataclass(slots=True)
class WorkflowTrace:
    execution_id: str
    correlation_id: str
    organization_id: UUID
    workflow_name: str
    node_id: str
    phase: str  # start | finish
    duration_ms: int = 0
    failure: bool = False
    retry_count: int = 0
    fallback_used: bool = False
    dependencies: tuple[str, ...] = ()
    outcome: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "organization_id": str(self.organization_id),
            "workflow_name": self.workflow_name,
            "node_id": self.node_id,
            "phase": self.phase,
            "duration_ms": self.duration_ms,
            "failure": self.failure,
            "retry_count": self.retry_count,
            "fallback_used": self.fallback_used,
            "dependencies": list(self.dependencies),
            "outcome": self.outcome,
            "metadata": dict(self.metadata),
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
        }


@dataclass(slots=True)
class EvaluationResult:
    evaluation_id: str
    correlation_id: str
    organization_id: UUID
    subject_type: str
    subject_id: str
    scores: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    signals: tuple[str, ...] = ()
    inputs_fingerprint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "correlation_id": self.correlation_id,
            "organization_id": str(self.organization_id),
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "scores": dict(self.scores),
            "overall": self.overall,
            "signals": list(self.signals),
            "inputs_fingerprint": self.inputs_fingerprint,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ProviderHealth:
    provider: str
    organization_id: UUID | None = None
    requests: int = 0
    successes: int = 0
    failures: int = 0
    timeouts: int = 0
    fallbacks: int = 0
    total_latency_ms: int = 0
    error_classes: dict[str, int] = field(default_factory=dict)

    @property
    def availability(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.successes / self.requests

    @property
    def average_latency_ms(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.total_latency_ms / self.requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "timeouts": self.timeouts,
            "fallbacks": self.fallbacks,
            "availability": round(self.availability, 4),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "error_classes": dict(self.error_classes),
        }


@dataclass(slots=True)
class ModelHealth:
    provider: str
    model: str
    requests: int = 0
    total_latency_ms: int = 0
    total_cost: float = 0.0
    cache_hits: int = 0
    approval_score_sum: float = 0.0
    approval_score_n: int = 0
    hallucination_reports: int = 0
    quality_score_sum: float = 0.0
    quality_score_n: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "requests": self.requests,
            "average_latency_ms": round(
                self.total_latency_ms / self.requests if self.requests else 0.0, 2
            ),
            "total_cost": round(self.total_cost, 6),
            "cache_effectiveness": round(
                self.cache_hits / self.requests if self.requests else 0.0, 4
            ),
            "approval_score": round(
                self.approval_score_sum / self.approval_score_n
                if self.approval_score_n
                else 0.0,
                4,
            ),
            "quality_score": round(
                self.quality_score_sum / self.quality_score_n
                if self.quality_score_n
                else 0.0,
                4,
            ),
            "hallucination_reports": self.hallucination_reports,
        }


@dataclass(slots=True)
class CostRecord:
    record_id: str
    organization_id: UUID
    category: CostCategory
    amount_usd: float
    correlation_id: str | None = None
    provider: str | None = None
    model: str | None = None
    workflow_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "organization_id": str(self.organization_id),
            "category": str(self.category),
            "amount_usd": self.amount_usd,
            "correlation_id": self.correlation_id,
            "provider": self.provider,
            "model": self.model,
            "workflow_name": self.workflow_name,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class OptimizationSignal:
    signal_id: str
    organization_id: UUID
    kind: str
    severity: str
    message: str
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "organization_id": str(self.organization_id),
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
        }
