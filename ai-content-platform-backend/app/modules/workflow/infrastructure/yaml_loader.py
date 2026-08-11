"""YAML workflow definition loader."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.modules.workflow.domain.models import (
    ConditionType,
    FallbackPolicy,
    FallbackStrategy,
    NodeCategory,
    NodeCondition,
    RetryPolicy,
    RetryStrategy,
    WorkflowDefinition,
    WorkflowNode,
    WorkflowStatus,
)


class YamlWorkflowLoader:
    def load_path(self, path: Path) -> WorkflowDefinition:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return self._parse(data)

    def load_dir(self, directory: Path) -> list[WorkflowDefinition]:
        definitions: list[WorkflowDefinition] = []
        for path in sorted(directory.glob("*.yaml")):
            definitions.append(self.load_path(path))
        for path in sorted(directory.glob("*.yml")):
            definitions.append(self.load_path(path))
        return definitions

    def _parse(self, raw: dict[str, Any]) -> WorkflowDefinition:
        root = raw.get("workflow") or raw
        name = str(root["name"])
        version = str(root.get("version", "1.0"))
        entry = str(root["entry"])
        nodes_raw = root.get("nodes") or []
        nodes: list[WorkflowNode] = []
        for item in nodes_raw:
            nodes.append(self._parse_node(item))

        status_raw = str(root.get("status") or WorkflowStatus.ACTIVE.value)
        created = self._parse_dt(root.get("created_at"))
        updated = self._parse_dt(root.get("updated_at"))
        return WorkflowDefinition(
            name=name,
            version=version,
            entry_node_id=entry,
            nodes=tuple(nodes),
            description=str(root.get("description") or ""),
            metadata=dict(root.get("metadata") or {}),
            status=WorkflowStatus(status_raw),
            created_at=created,
            updated_at=updated,
            author=str(root.get("author") or ""),
            compatible_engine_version=str(root.get("compatible_engine_version") or "1"),
            timeout_ms=root.get("timeout_ms"),
        )

    def _parse_node(self, item: dict[str, Any]) -> WorkflowNode:
        retry_raw = item.get("retry") or {}
        fallback_raw = item.get("fallback")
        transitions = item.get("transitions") or []
        conditions: list[NodeCondition] = []
        for tr in transitions:
            when = tr.get("when") or {"type": "always"}
            conditions.append(
                NodeCondition(
                    type=ConditionType(str(when.get("type", "always"))),
                    target_node_id=str(tr["to"]),
                    expression=when.get("expression"),
                )
            )
        fallback = None
        if fallback_raw:
            fallback = FallbackPolicy(
                strategy=FallbackStrategy(str(fallback_raw.get("strategy", "stop"))),
                alternative_node_id=fallback_raw.get("alternative_node_id")
                or fallback_raw.get("to"),
            )
        category = str(item.get("category") or NodeCategory.SYSTEM.value)
        return WorkflowNode(
            id=str(item["id"]),
            name=str(item.get("name") or item["id"]),
            type=str(item["type"]),
            inputs=tuple(item.get("inputs") or ()),
            outputs=tuple(item.get("outputs") or ()),
            conditions=tuple(conditions),
            retry=RetryPolicy(
                strategy=RetryStrategy(str(retry_raw.get("strategy", "none"))),
                max_attempts=int(retry_raw.get("max_attempts", 1)),
                delay_ms=int(retry_raw.get("delay_ms", 0)),
                max_delay_ms=int(retry_raw.get("max_delay_ms", 60_000)),
            ),
            fallback=fallback,
            timeout_ms=item.get("timeout_ms"),
            config=dict(item.get("config") or {}),
            metadata=dict(item.get("metadata") or {}),
            terminal=bool(item.get("terminal", False)),
            category=category,
        )

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
