"""Consensus developer API — reports, comparison, replay (APP_DEBUG or admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.schemas.envelope import success_response
from app.core.config import get_settings
from app.core.constants import MembershipRole
from app.core.security import require_role
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.consensus.application.factory import ConsensusEngineFactory
from app.modules.consensus.application.engine import DefaultConsensusEngine

router = APIRouter(prefix="/consensus", tags=["consensus"])

_engine: DefaultConsensusEngine | None = None


def get_consensus_engine() -> DefaultConsensusEngine:
    global _engine
    if _engine is None:
        _engine = ConsensusEngineFactory.create()
    return _engine


def _require_dev_mode(user: AuthenticatedUser) -> None:
    settings = get_settings()
    if settings.APP_DEBUG:
        return
    role = getattr(user, "role", None) or getattr(user, "membership_role", None)
    role_s = str(role).lower()
    if role_s not in {"owner", "admin", str(MembershipRole.OWNER).lower()}:
        raise HTTPException(
            status_code=403, detail="Consensus reports require debug mode or owner role"
        )


@router.get("/runs/{run_id}")
async def get_run_report(
    run_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    engine: DefaultConsensusEngine = Depends(get_consensus_engine),
) -> dict:
    _require_dev_mode(current_user)
    run = engine.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Consensus run not found")
    return success_response(run.to_report(), request_id=getattr(request.state, "request_id", ""))


@router.get("/runs")
async def list_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    engine: DefaultConsensusEngine = Depends(get_consensus_engine),
) -> dict:
    _require_dev_mode(current_user)
    runs = await engine._repo.list_runs(current_user.organization_id, limit=limit)  # noqa: SLF001
    return success_response(
        {"runs": [r.to_report() for r in runs]},
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/runs/{run_id}/comparison")
async def provider_comparison(
    run_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    engine: DefaultConsensusEngine = Depends(get_consensus_engine),
) -> dict:
    _require_dev_mode(current_user)
    run = engine.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Consensus run not found")
    report = run.to_report()
    return success_response(
        {
            "run_id": run_id,
            "candidates": report.get("candidates"),
            "evaluations": report.get("evaluations"),
            "judge": report.get("judge"),
            "merge": report.get("merge"),
            "cost_report": report.get("cost_report"),
            "latency_report": report.get("latency_report"),
            "confidence_report": report.get("confidence_report"),
        },
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/runs/{run_id}/replay")
async def replay_run(
    run_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    engine: DefaultConsensusEngine = Depends(get_consensus_engine),
) -> dict:
    _require_dev_mode(current_user)
    snap = (
        engine._repo.get_replay_snapshot(run_id)  # noqa: SLF001
        if hasattr(engine._repo, "get_replay_snapshot")
        else None
    )
    run = engine.get_run(run_id)
    if run is None and snap is None:
        raise HTTPException(status_code=404, detail="Consensus replay not found")
    return success_response(
        {"run_id": run_id, "snapshot": snap or (run.to_report() if run else {})},
        request_id=getattr(request.state, "request_id", ""),
    )
