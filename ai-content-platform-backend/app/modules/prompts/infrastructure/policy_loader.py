"""YAML Prompt Policy loader — mirrors planner/knowledge resolve order."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.prompts.domain.models import PromptPolicy

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "prompts" / "policies"


class YamlPromptPolicyLoader:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or _DEFAULT_DIR

    def load(self, policy_id: str = "default") -> PromptPolicy:
        path = self._resolve_path(policy_id)
        raw: dict[str, Any] = {}
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        return self._from_dict(policy_id, raw)

    def _resolve_path(self, policy_id: str) -> Path:
        if policy_id and policy_id != "default":
            org = self._dir / "orgs" / f"{policy_id}.yaml"
            if org.exists():
                return org
            named = self._dir / f"{policy_id}.yaml"
            if named.exists():
                return named
        return self._dir / "default_policy.yaml"

    @staticmethod
    def _from_dict(policy_id: str, raw: dict[str, Any]) -> PromptPolicy:
        compliance = raw.get("compliance") or {}
        return PromptPolicy(
            policy_id=str(raw.get("policy_id") or policy_id or "default"),
            max_prompt_tokens=int(raw.get("max_prompt_tokens", 12_000)),
            max_section_tokens=int(raw.get("max_section_tokens", 4_000)),
            allowed_capabilities=tuple(
                str(x) for x in (raw.get("allowed_capabilities") or [])
            ),
            denied_capabilities=tuple(
                str(x) for x in (raw.get("denied_capabilities") or [])
            ),
            restricted_variables=tuple(
                str(x) for x in (raw.get("restricted_variables") or [])
            ),
            forbidden_sections=tuple(
                str(x) for x in (raw.get("forbidden_sections") or [])
            ),
            provider_constraints=dict(raw.get("provider_constraints") or {}),
            forbidden_substrings=tuple(
                str(x) for x in (compliance.get("forbidden_substrings") or [])
            ),
            required_sections=tuple(
                str(x) for x in (compliance.get("required_sections") or [])
            ),
        )
