"""Prompt registry — loads versioned prompts from YAML and DB, logs LLM calls."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.llm.base import CompletionResult
from app.infrastructure.postgres.models.ai_ops import LlmCall, PromptVersion

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "configs" / "prompts"


class PromptRegistryService:
    """Loads prompts from YAML configs and the prompt_versions DB table.

    Also provides logging of LLM calls with full telemetry.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._yaml_cache: dict[str, dict[str, Any]] = {}

    def _load_yaml(self, name: str) -> dict[str, Any] | None:
        if name in self._yaml_cache:
            return self._yaml_cache[name]

        path = _PROMPTS_DIR / f"{name}.yaml"
        if not path.exists():
            return None

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        self._yaml_cache[name] = data
        return data

    async def get_latest(self, name: str) -> dict[str, Any] | None:
        """Get the latest prompt by name — check DB first, fall back to YAML."""
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.name == name, PromptVersion.is_active.is_(True))
            .order_by(PromptVersion.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return {
                "id": str(row.id),
                "name": row.name,
                "version": row.version,
                "body": row.body,
                "variables_schema": row.variables_schema,
                "eval_notes": row.eval_notes,
            }

        yaml_data = self._load_yaml(name)
        if yaml_data:
            return {
                "id": None,
                "name": yaml_data.get("name", name),
                "version": yaml_data.get("version", "1.0"),
                "body": yaml_data.get("body", ""),
                "variables_schema": yaml_data.get("variables"),
                "eval_notes": yaml_data.get("eval_notes"),
            }
        return None

    def render(self, prompt_data: dict[str, Any], variables: dict[str, str]) -> str:
        """Render a prompt template with the given variables."""
        body = prompt_data.get("body", "")
        for key, value in variables.items():
            body = body.replace(f"{{{key}}}", value or "")
        return body

    async def log_llm_call(
        self,
        *,
        organization_id: uuid.UUID | None,
        prompt_name: str,
        prompt_version: str,
        result: CompletionResult,
        input_text: str,
        correlation_id: str = "",
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        """Persist an LLM call record for observability and cost tracking."""
        import hashlib

        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:64]

        call = LlmCall(
            organization_id=organization_id,
            provider=result.provider,
            model=result.model,
            input_hash=input_hash,
            input_text=input_text[:10_000],
            output_text=result.text[:10_000],
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_estimate=result.cost_estimate,
            correlation_id=correlation_id,
            status=status,
            error_message=error_message,
        )
        self._session.add(call)
        await self._session.flush()

        logger.info(
            "LLM call logged: prompt=%s version=%s provider=%s model=%s latency=%dms",
            prompt_name,
            prompt_version,
            result.provider,
            result.model,
            result.latency_ms,
        )
