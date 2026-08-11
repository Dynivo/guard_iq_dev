"""Prompt catalog routes — read-only list of YAML prompt definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.prompts.infrastructure.yaml_registry import YamlPromptRegistry

router = APIRouter(prefix="/prompts", tags=["prompts"])

_registry = YamlPromptRegistry()


@router.get("")
async def list_prompts(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> dict:
    """List versioned prompts from configs/prompts (read-only catalog)."""
    items = await _registry.list_catalog()
    return success_response(
        {"items": items, "count": len(items)},
        request_id=getattr(request.state, "request_id", ""),
    )
