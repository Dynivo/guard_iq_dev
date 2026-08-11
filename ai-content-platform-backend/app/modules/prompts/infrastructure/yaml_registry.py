"""YAML + in-memory Prompt Registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.prompts.domain.models import (
    ApprovalStatus,
    PromptDefinition,
    PromptSection,
    PromptStatus,
    PromptVariableSpec,
)

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "prompts"


class YamlPromptRegistry:
    """Loads versioned prompts from configs/prompts; supports in-memory register."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or _DEFAULT_DIR
        self._memory: dict[str, dict[str, PromptDefinition]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self._dir.exists():
            return
        for path in sorted(self._dir.glob("*.yaml")):
            if path.parent.name in {"partials", "schemas", "eval"}:
                continue
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                continue
            definition = self._from_yaml(raw, path.stem)
            self._memory.setdefault(definition.name, {})[definition.version] = definition

    @staticmethod
    def _from_yaml(raw: dict[str, Any], fallback_name: str) -> PromptDefinition:
        name = str(raw.get("name") or fallback_name)
        version = str(raw.get("version") or "1.0")
        vars_raw = raw.get("variables") or []
        variables = tuple(
            PromptVariableSpec(
                name=str(v.get("name")),
                type=str(v.get("type") or "text"),
                required=bool(v.get("required", True)),
                description=str(v.get("description") or ""),
            )
            for v in vars_raw
            if isinstance(v, dict) and v.get("name")
        )
        sections_raw = raw.get("sections") or {}
        sections: list[PromptSection] = []
        if isinstance(sections_raw, dict):
            for i, (key, body) in enumerate(sections_raw.items()):
                sections.append(PromptSection(name=str(key), body=str(body), order=i))

        # Many prompts use system / user_template / body instead of sections
        system = str(raw.get("system") or "").strip()
        user_template = str(raw.get("user_template") or "").strip()
        body = str(raw.get("body") or raw.get("template") or "").strip()
        description = str(raw.get("description") or "").strip()
        if system:
            sections.append(PromptSection(name="system", body=system, order=len(sections)))
        if user_template:
            sections.append(
                PromptSection(name="user_template", body=user_template, order=len(sections))
            )
        if body and not any(s.name == "body" for s in sections):
            sections.append(PromptSection(name="body", body=body, order=len(sections)))
        if description and not sections:
            sections.append(
                PromptSection(name="description", body=description, order=0)
            )

        template = body or "\n\n".join(f"## {s.name}\n{s.body}" for s in sections)
        status = PromptStatus(str(raw.get("status") or "active"))
        approval = ApprovalStatus(str(raw.get("approval_status") or "approved"))
        return PromptDefinition(
            id=str(raw.get("id") or f"{name}:{version}"),
            name=name,
            version=version,
            capability=str(raw.get("capability") or name),
            status=status,
            approval_status=approval,
            template=template,
            sections=tuple(sections),
            variables=variables,
            required_inputs=tuple(str(x) for x in (raw.get("required_inputs") or [])),
            optional_inputs=tuple(str(x) for x in (raw.get("optional_inputs") or [])),
            provider_constraints=dict(raw.get("provider_constraints") or {}),
            supported_models=tuple(str(x) for x in (raw.get("supported_models") or [])),
            schema_id=str(raw.get("schema_id") or "json"),
            tags=tuple(str(x) for x in (raw.get("tags") or [])),
            created_by=str(raw.get("owner") or raw.get("created_by") or "platform"),
            metadata={
                **dict(raw.get("metadata") or {}),
                **({"description": description} if description else {}),
            },
        )

    async def get_latest(self, name: str) -> PromptDefinition | None:
        versions = self._memory.get(name) or {}
        active = [
            d
            for d in versions.values()
            if d.status == PromptStatus.ACTIVE
            and d.approval_status == ApprovalStatus.APPROVED
        ]
        if not active:
            active = list(versions.values())
        if not active:
            return None
        active.sort(key=lambda d: d.version, reverse=True)
        return active[0]

    async def get_version(self, name: str, version: str) -> PromptDefinition | None:
        return (self._memory.get(name) or {}).get(version)

    async def register(self, definition: PromptDefinition) -> str:
        self._memory.setdefault(definition.name, {})[definition.version] = definition
        return definition.id

    async def list_names(self) -> list[str]:
        return sorted(self._memory.keys())

    async def list_catalog(self) -> list[dict[str, Any]]:
        """Flatten all loaded prompt versions for the Prompts UI."""
        items: list[dict[str, Any]] = []
        for name in sorted(self._memory.keys()):
            versions = self._memory.get(name) or {}
            for version in sorted(versions.keys(), reverse=True):
                d = versions[version]
                sections = [
                    {"name": s.name, "body": s.body, "order": s.order} for s in d.sections
                ]
                body = (d.template or "").strip()
                if not body and sections:
                    body = "\n\n".join(f"## {s['name']}\n{s['body']}" for s in sections)
                preview = body[:400] if body else str((d.metadata or {}).get("description") or "")
                items.append(
                    {
                        "id": d.id,
                        "name": d.name,
                        "version": d.version,
                        "capability": d.capability,
                        "status": str(d.status.value if hasattr(d.status, "value") else d.status),
                        "approval_status": str(
                            d.approval_status.value
                            if hasattr(d.approval_status, "value")
                            else d.approval_status
                        ),
                        "section_count": len(d.sections),
                        "variable_count": len(d.variables),
                        "tags": list(d.tags),
                        "owner": d.created_by,
                        "preview": preview,
                        "body": body,
                        "sections": sections,
                        "description": (d.metadata or {}).get("description") or "",
                    }
                )
        return items
