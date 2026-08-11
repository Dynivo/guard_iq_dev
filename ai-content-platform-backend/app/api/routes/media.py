"""Authenticated media delivery via StorageProvider + Delivery Strategy stream URLs.

Clients must never hit public buckets. Default strategy (backend_stream) serves
bytes only after auth + org-prefix checks.
"""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.constants import MembershipRole
from app.core.exceptions import AuthorizationError
from app.core.security import require_role
from app.infrastructure.storage.factory import get_storage_provider
from app.modules.auth.domain.entities import AuthenticatedUser

router = APIRouter(prefix="/media", tags=["media"])


def _assert_org_access(object_key: str, current_user: AuthenticatedUser) -> None:
    if ".." in object_key:
        raise AuthorizationError("Invalid media path")
    org_prefix = f"{current_user.organization_id}/"
    if object_key.startswith(org_prefix):
        return
    if f"/{current_user.organization_id}/" in f"/{object_key}":
        return
    raise AuthorizationError("Not allowed to access this media object")


def _guess_content_type(object_key: str) -> str:
    guessed, _ = mimetypes.guess_type(object_key)
    return guessed or "application/octet-stream"


@router.get("/objects/{object_key:path}")
async def get_media_object(
    object_key: str,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> Response:
    """Stream object bytes from StorageProvider (local or S3)."""
    _assert_org_access(object_key, current_user)
    storage = get_storage_provider()
    data = storage.get_bytes(object_key)
    return Response(content=data, media_type=_guess_content_type(object_key))


@router.get("/local/{object_key:path}")
async def get_local_media_compat(
    object_key: str,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> Response:
    """Deprecated alias for /media/objects — kept for transitional clients."""
    return await get_media_object(object_key, current_user)
