"""In-memory workflow definition registry with active-version preference."""

from __future__ import annotations

from pathlib import Path

from app.modules.workflow.application.validator import DefaultWorkflowValidator
from app.modules.workflow.domain.models import WorkflowDefinition, WorkflowStatus
from app.modules.workflow.domain.ports import NodeRegistry, WorkflowLoader
from app.shared.result import Failure


class InMemoryWorkflowRegistry:
    def __init__(
        self,
        *,
        known_types: set[str] | None = None,
        lint_on_register: bool = False,
    ) -> None:
        self._defs: dict[str, dict[str, WorkflowDefinition]] = {}
        self._known_types = known_types
        self._lint_on_register = lint_on_register
        self._linter = DefaultWorkflowValidator()

    def set_known_types(self, types: set[str]) -> None:
        self._known_types = types

    def register(self, definition: WorkflowDefinition, *, lint: bool | None = None) -> None:
        do_lint = self._lint_on_register if lint is None else lint
        if do_lint and self._known_types is not None:
            result = self._linter.validate(definition, self._known_types)
            if isinstance(result, Failure):
                raise ValueError(f"{result.code}: {result.message}")
        self._defs.setdefault(definition.name, {})[definition.version] = definition

    def get(self, name: str, version: str | None = None) -> WorkflowDefinition:
        versions = self._defs.get(name)
        if not versions:
            raise KeyError(f"Unknown workflow '{name}'")
        if version is not None:
            if version not in versions:
                raise KeyError(f"Unknown workflow '{name}' version '{version}'")
            return versions[version]

        active = [d for d in versions.values() if d.status == WorkflowStatus.ACTIVE]
        if active:
            return sorted(active, key=lambda d: d.version)[-1]
        latest_key = sorted(versions.keys())[-1]
        return versions[latest_key]

    def list_names(self) -> list[str]:
        return sorted(self._defs.keys())

    def invalidate(self, name: str | None = None) -> None:
        if name is None:
            self._defs.clear()
        else:
            self._defs.pop(name, None)


class CachedWorkflowRegistry:
    """Caches loaded YAML definitions; run path never re-reads disk.

    ``invalidate(name=)`` drops cache entries; ``reload()`` re-reads the directory.
    """

    def __init__(
        self,
        loader: WorkflowLoader,
        workflows_dir: Path,
        *,
        node_registry: NodeRegistry | None = None,
        lint_on_register: bool = False,
    ) -> None:
        self._loader = loader
        self._dir = workflows_dir
        self._node_registry = node_registry
        self._lint_on_register = lint_on_register
        self._inner = InMemoryWorkflowRegistry(
            known_types=node_registry.known_types() if node_registry else None,
            lint_on_register=lint_on_register and node_registry is not None,
        )
        self.reload()

    def register(self, definition: WorkflowDefinition, *, lint: bool | None = None) -> None:
        if self._node_registry is not None:
            self._inner.set_known_types(self._node_registry.known_types())
        self._inner.register(definition, lint=lint)

    def get(self, name: str, version: str | None = None) -> WorkflowDefinition:
        return self._inner.get(name, version)

    def list_names(self) -> list[str]:
        return self._inner.list_names()

    def invalidate(self, name: str | None = None) -> None:
        self._inner.invalidate(name)

    def reload(self) -> None:
        self._inner.invalidate()
        if self._node_registry is not None:
            self._inner.set_known_types(self._node_registry.known_types())
        if not self._dir.is_dir():
            return
        for definition in self._loader.load_dir(self._dir):
            # Soft-load from disk (scaffolds may reference future types);
            # engine still validates at run time.
            self._inner.register(definition, lint=False)
