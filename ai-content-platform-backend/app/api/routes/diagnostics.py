"""Diagnostics export — a downloadable bundle the client can send to their
agency when something goes wrong (recent job history, environment info, and
a tail of the on-disk log file)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.jobs.application.use_cases import ExportDiagnosticsUseCase

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/export")
async def export_diagnostics(
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    zip_bytes, filename = await ExportDiagnosticsUseCase(session).execute(
        current_user.organization_id
    )
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
