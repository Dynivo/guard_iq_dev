"""Prompt Policy Engine — org/provider/size/compliance gates after Optimize."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.prompts.domain.models import (
    CompiledPrompt,
    PolicyResult,
    PromptDefinition,
    PromptPolicy,
)
from app.modules.prompts.infrastructure.policy_loader import YamlPromptPolicyLoader


class DefaultPromptPolicyEngine:
    def __init__(self, loader: YamlPromptPolicyLoader | None = None) -> None:
        self._loader = loader or YamlPromptPolicyLoader()

    def apply(
        self,
        definition: PromptDefinition,
        compiled: CompiledPrompt,
        variables: dict[str, str],
        *,
        organization_id: uuid.UUID | None,
        capability: str,
        policy: PromptPolicy | None = None,
    ) -> PolicyResult:
        pol = policy or self._resolve_policy(organization_id)
        errors: list[str] = []

        cap = capability or definition.capability
        if pol.denied_capabilities and cap in pol.denied_capabilities:
            errors.append(f"capability denied by policy: {cap}")
        if pol.allowed_capabilities and cap not in pol.allowed_capabilities:
            errors.append(f"capability not allowed by policy: {cap}")

        if compiled.token_estimate > pol.max_prompt_tokens:
            errors.append(
                f"prompt size {compiled.token_estimate} exceeds policy max "
                f"{pol.max_prompt_tokens}"
            )

        for name, body in compiled.sections.items():
            estimate = max(1, len(body) // 4) if body else 0
            if estimate > pol.max_section_tokens:
                errors.append(
                    f"section '{name}' size {estimate} exceeds policy max "
                    f"{pol.max_section_tokens}"
                )
            if name in pol.forbidden_sections:
                errors.append(f"forbidden section present: {name}")

        for name in pol.restricted_variables:
            val = (variables.get(name) or "").strip()
            if val:
                errors.append(f"restricted variable must be empty: {name}")

        for req in pol.required_sections:
            if req not in compiled.sections or not (compiled.sections.get(req) or "").strip():
                errors.append(f"required section missing: {req}")

        blob = f"{compiled.system_message}\n{compiled.text}".lower()
        for needle in pol.forbidden_substrings:
            if needle and needle.lower() in blob:
                errors.append(f"compliance forbidden substring: {needle}")

        metrics: dict[str, Any] = {
            "policy_id": pol.policy_id,
            "provider_constraints": dict(pol.provider_constraints),
            "max_prompt_tokens": pol.max_prompt_tokens,
        }
        # Merge definition-level provider hints into metrics (no SDK calls)
        if definition.provider_constraints:
            metrics["definition_provider_constraints"] = dict(
                definition.provider_constraints
            )

        return PolicyResult(
            allowed=len(errors) == 0,
            errors=tuple(errors),
            policy_id=pol.policy_id,
            metrics=metrics,
        )

    def _resolve_policy(self, organization_id: uuid.UUID | None) -> PromptPolicy:
        if organization_id is not None and organization_id.int != 0:
            return self._loader.load(str(organization_id))
        return self._loader.load("default")
