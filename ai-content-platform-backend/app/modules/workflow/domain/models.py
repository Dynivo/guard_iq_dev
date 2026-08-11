"""Workflow engine domain models — domain-agnostic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


ENGINE_COMPAT_VERSION = "1"


class RetryStrategy(str, Enum):
    NONE = "none"
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"


class FallbackStrategy(str, Enum):
    ALTERNATIVE_NODE = "alternative_node"
    SKIP = "skip"
    STOP = "stop"


class ConditionType(str, Enum):
    ALWAYS = "always"
    SUCCESS = "success"
    FAILURE = "failure"
    EXPRESSION = "expression"


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class NodeCategory(str, Enum):
    SYSTEM = "system"
    AI = "ai"
    KNOWLEDGE = "knowledge"
    CONTENT = "content"
    IMAGE = "image"
    STORAGE = "storage"
    REVIEW = "review"
    LEARNING = "learning"
    ANALYTICS = "analytics"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    strategy: RetryStrategy = RetryStrategy.NONE
    max_attempts: int = 1
    delay_ms: int = 0
    max_delay_ms: int = 60_000


@dataclass(frozen=True, slots=True)
class FallbackPolicy:
    strategy: FallbackStrategy = FallbackStrategy.STOP
    alternative_node_id: str | None = None


@dataclass(frozen=True, slots=True)
class NodeCondition:
    type: ConditionType
    target_node_id: str
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    id: str
    name: str
    type: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    conditions: tuple[NodeCondition, ...] = ()
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    fallback: FallbackPolicy | None = None
    timeout_ms: int | None = None
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    terminal: bool = False
    category: str = NodeCategory.SYSTEM.value


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    name: str
    version: str
    entry_node_id: str
    nodes: tuple[WorkflowNode, ...]
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author: str = ""
    compatible_engine_version: str = ENGINE_COMPAT_VERSION
    timeout_ms: int | None = None

    def node_map(self) -> dict[str, WorkflowNode]:
        return {n.id: n for n in self.nodes}

    def get_node(self, node_id: str) -> WorkflowNode | None:
        return self.node_map().get(node_id)


@dataclass
class CancelToken:
    """Cooperative cancellation token for workflow execution."""

    _cancelled: bool = False
    reason: str = ""

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self, reason: str = "cancelled") -> None:
        self._cancelled = True
        self.reason = reason


@dataclass(frozen=True, slots=True)
class SimulationOptions:
    """Dry-run / mock mode — no external side effects for unregistered types."""

    dry_run: bool = True
    mock_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    skip_categories: tuple[str, ...] = (
        NodeCategory.AI.value,
        NodeCategory.STORAGE.value,
        NodeCategory.IMAGE.value,
    )


@dataclass
class WorkflowContext:
    """Mutable execution context with scoped bags. No globals.

    ``data`` and ``shared`` are the same dict (backward-compatible get/set/update).
    """

    correlation_id: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    request_id: str = ""
    workflow_name: str = ""
    workflow_version: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    shared: dict[str, Any] = field(default_factory=dict)
    request: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] = field(default_factory=dict)
    node: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Unify shared ↔ data so existing get/set keep working.
        if self.data is not self.shared:
            if self.data and not self.shared:
                self.shared = self.data
            elif self.shared and not self.data:
                self.data = self.shared
            else:
                merged = {**self.shared, **self.data}
                self.data = merged
                self.shared = merged
        self.request.setdefault("correlation_id", self.correlation_id)
        if self.request_id:
            self.request.setdefault("request_id", self.request_id)
        if self.organization_id is not None:
            self.request.setdefault("organization_id", str(self.organization_id))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def update(self, values: dict[str, Any]) -> None:
        self.data.update(values)

    def set_node_local(self, key: str, value: Any) -> None:
        self.node[key] = value

    def clear_node_scope(self) -> None:
        self.node.clear()

    def add_error(self, *, node_id: str, message: str, code: str = "NODE_ERROR") -> None:
        self.errors.append(
            {
                "node_id": node_id,
                "code": code,
                "message": message,
                "at": _utcnow().isoformat(),
            }
        )


@dataclass(frozen=True, slots=True)
class NodeOutcome:
    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    cancelled: bool = False
    timed_out: bool = False


@dataclass
class WorkflowExecution:
    execution_id: str
    workflow_name: str
    workflow_version: str
    status: str = "pending"
    current_node_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    success: bool
    execution_id: str
    workflow_name: str
    workflow_version: str
    context: WorkflowContext
    error_code: str | None = None
    error_message: str | None = None
    metrics_summary: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionHistoryRecord:
    execution_id: str
    event: str
    timestamp: datetime
    node_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
