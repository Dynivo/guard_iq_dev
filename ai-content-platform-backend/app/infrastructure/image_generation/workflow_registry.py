"""File-backed ComfyUI workflow registry — never embeds graphs in adapters."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import yaml

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.image.application.cache import InMemoryWorkflowCache
from app.modules.image.domain.models import WorkflowDescriptor

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class FileComfyWorkflowRegistry:
    def __init__(
        self,
        registry_dir: Path | None = None,
        cache: InMemoryWorkflowCache | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[3] / "configs" / "image" / "workflows"
        self._dir = registry_dir or root
        self._cache = cache or InMemoryWorkflowCache()
        self._index = self._load_index()

    def _load_index(self) -> dict[str, WorkflowDescriptor]:
        path = self._dir / "registry.yaml"
        if not path.exists():
            return {}
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = raw.get("workflows") or []
        out: dict[str, WorkflowDescriptor] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            desc = WorkflowDescriptor(
                workflow_id=str(item.get("workflow_id") or ""),
                version=str(item.get("version") or "1"),
                provider=str(item.get("provider") or "comfyui"),
                model=str(item.get("model") or ""),
                path=str(item.get("path") or ""),
                parameters=dict(item.get("parameters") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
            out[f"{desc.workflow_id}@{desc.version}"] = desc
            out[desc.workflow_id] = desc  # latest alias → last wins; prefer explicit version
        # Prefer first occurrence as default alias for each id
        seen: set[str] = set()
        for item in items:
            wid = str(item.get("workflow_id") or "")
            if wid and wid not in seen:
                seen.add(wid)
                out[wid] = WorkflowDescriptor(
                    workflow_id=wid,
                    version=str(item.get("version") or "1"),
                    provider=str(item.get("provider") or "comfyui"),
                    model=str(item.get("model") or ""),
                    path=str(item.get("path") or ""),
                    parameters=dict(item.get("parameters") or {}),
                    metadata=dict(item.get("metadata") or {}),
                )
        return out

    def get(self, workflow_id: str, version: str | None = None) -> WorkflowDescriptor:
        key = f"{workflow_id}@{version}" if version else workflow_id
        cached = self._cache.get_descriptor(key)
        if cached:
            return cached
        desc = self._index.get(key) or self._index.get(workflow_id)
        if desc is None:
            raise NotFoundError("ComfyWorkflow", key)
        self._cache.put_descriptor(key, desc)
        return desc

    def load_graph(self, descriptor: WorkflowDescriptor) -> dict[str, Any]:
        cache_key = f"{descriptor.workflow_id}@{descriptor.version}"
        cached = self._cache.get_graph(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)
        path = self._dir / descriptor.path
        if not path.exists():
            raise NotFoundError("ComfyWorkflowGraph", descriptor.path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValidationError("Workflow graph must be a JSON object")
        self._cache.put_graph(cache_key, data)
        return copy.deepcopy(data)

    def list_workflows(self) -> list[WorkflowDescriptor]:
        seen: set[str] = set()
        out: list[WorkflowDescriptor] = []
        for key, desc in self._index.items():
            if "@" not in key:
                continue
            if desc.workflow_id in seen:
                continue
            seen.add(desc.workflow_id)
            out.append(desc)
        return out

    def render_graph(self, descriptor: WorkflowDescriptor, params: dict[str, Any]) -> dict[str, Any]:
        graph = self.load_graph(descriptor)
        merged = {**descriptor.parameters, **params}

        def _sub(obj: Any) -> Any:
            if isinstance(obj, str):
                def repl(m: re.Match[str]) -> str:
                    key = m.group(1)
                    if key not in merged:
                        return m.group(0)
                    val = merged[key]
                    return str(val)

                if _PLACEHOLDER.fullmatch(obj):
                    key = obj[2:-2]
                    if key in merged:
                        return merged[key]
                return _PLACEHOLDER.sub(repl, obj)
            if isinstance(obj, list):
                return [_sub(x) for x in obj]
            if isinstance(obj, dict):
                return {k: _sub(v) for k, v in obj.items()}
            return obj

        return _sub(graph)
