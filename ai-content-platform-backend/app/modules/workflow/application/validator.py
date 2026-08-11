"""Workflow definition structural validation + lint rules."""

from __future__ import annotations

from collections import defaultdict, deque

from app.modules.workflow.domain.models import ENGINE_COMPAT_VERSION, WorkflowDefinition
from app.shared.result import Result, fail, ok


class DefaultWorkflowValidator:
    """Validates and lints workflow definitions before registration/execution."""

    def validate(
        self,
        definition: WorkflowDefinition,
        known_types: set[str],
    ) -> Result[WorkflowDefinition]:
        if not definition.name.strip():
            return fail("INVALID_NAME", "Workflow name is required")
        if not definition.version.strip():
            return fail("INVALID_VERSION", "Workflow version is required")
        if not definition.nodes:
            return fail("EMPTY_WORKFLOW", "Workflow must declare at least one node")

        ids = [n.id for n in definition.nodes]
        if len(ids) != len(set(ids)):
            return fail("DUPLICATE_NODE_ID", "Duplicate node ids in workflow definition")

        node_map = definition.node_map()
        if definition.entry_node_id not in node_map:
            return fail(
                "MISSING_ENTRY",
                f"Entry node '{definition.entry_node_id}' not found",
            )

        for node in definition.nodes:
            if node.type not in known_types:
                return fail(
                    "UNKNOWN_NODE_TYPE",
                    f"Unknown node type '{node.type}' on node '{node.id}'",
                )
            for cond in node.conditions:
                if cond.target_node_id not in node_map:
                    return fail(
                        "MISSING_TARGET",
                        f"Node '{node.id}' transitions to unknown '{cond.target_node_id}'",
                    )
                if cond.target_node_id == node.id:
                    return fail(
                        "SELF_TRANSITION",
                        f"Node '{node.id}' has a self-transition",
                    )
            if node.fallback and node.fallback.alternative_node_id:
                alt = node.fallback.alternative_node_id
                if alt not in node_map:
                    return fail(
                        "MISSING_FALLBACK",
                        f"Node '{node.id}' fallback target '{alt}' not found",
                    )
            if (
                node.retry.max_attempts > 100
                and any(c.target_node_id == node.id for c in node.conditions)
            ):
                return fail(
                    "INFINITE_RETRY_LOOP",
                    f"Node '{node.id}' looks like an infinite retry loop",
                )

        cycle = self._find_cycle(definition)
        if cycle:
            return fail("CYCLE_DETECTED", f"Cycle detected: {' -> '.join(cycle)}")

        unreachable = self._unreachable(definition)
        if unreachable:
            return fail(
                "UNREACHABLE_NODES",
                f"Unreachable nodes: {', '.join(sorted(unreachable))}",
            )

        dead = self._dead_nodes(definition)
        if dead:
            return fail(
                "DEAD_NODES",
                f"Dead nodes (non-terminal without outbound edges): {', '.join(sorted(dead))}",
            )

        # Soft compat check — only fail when major differs and explicit
        if definition.compatible_engine_version:
            want = definition.compatible_engine_version.split(".")[0]
            have = ENGINE_COMPAT_VERSION.split(".")[0]
            if want != have and definition.metadata.get("strict_engine_version"):
                return fail(
                    "INCOMPATIBLE_ENGINE",
                    f"Workflow requires engine {definition.compatible_engine_version}, "
                    f"running {ENGINE_COMPAT_VERSION}",
                )

        return ok(definition)

    def _unreachable(self, definition: WorkflowDefinition) -> set[str]:
        graph: dict[str, list[str]] = defaultdict(list)
        for node in definition.nodes:
            for cond in node.conditions:
                graph[node.id].append(cond.target_node_id)
            if node.fallback and node.fallback.alternative_node_id:
                graph[node.id].append(node.fallback.alternative_node_id)

        seen: set[str] = set()
        q: deque[str] = deque([definition.entry_node_id])
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in graph[cur]:
                if nxt not in seen:
                    q.append(nxt)
        all_ids = {n.id for n in definition.nodes}
        return all_ids - seen

    def _dead_nodes(self, definition: WorkflowDefinition) -> set[str]:
        dead: set[str] = set()
        for node in definition.nodes:
            if node.terminal:
                continue
            if not node.conditions and not (
                node.fallback and node.fallback.alternative_node_id
            ):
                dead.add(node.id)
        return dead

    def _find_cycle(self, definition: WorkflowDefinition) -> list[str] | None:
        graph: dict[str, list[str]] = defaultdict(list)
        for node in definition.nodes:
            for cond in node.conditions:
                graph[node.id].append(cond.target_node_id)
            if node.fallback and node.fallback.alternative_node_id:
                graph[node.id].append(node.fallback.alternative_node_id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n.id: WHITE for n in definition.nodes}
        parent: dict[str, str | None] = {n.id: None for n in definition.nodes}

        def dfs(u: str) -> list[str] | None:
            color[u] = GRAY
            for v in graph[u]:
                if color[v] == GRAY:
                    cycle = [v, u]
                    cur = u
                    while cur != v and parent[cur] is not None:
                        cur = parent[cur]  # type: ignore[assignment]
                        cycle.append(cur)
                    cycle.reverse()
                    return cycle
                if color[v] == WHITE:
                    parent[v] = u
                    found = dfs(v)
                    if found:
                        return found
            color[u] = BLACK
            return None

        for node in definition.nodes:
            if color[node.id] == WHITE:
                found = dfs(node.id)
                if found:
                    return found
        return None


# Alias for docs / registration-time lint
WorkflowLinter = DefaultWorkflowValidator
