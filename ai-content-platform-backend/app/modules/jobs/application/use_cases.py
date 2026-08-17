"""Jobs application use cases — no raw SQL in routes."""

from __future__ import annotations

import io
import json
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.infrastructure.postgres.models.imaging import ImageJob
from app.infrastructure.postgres.models.jobs import Job


class ListJobsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(Job)
                .where(Job.organization_id == org_id)
                .order_by(Job.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        items: list[dict[str, Any]] = [
            {
                "id": str(j.id),
                "type": j.job_type,
                "status": j.status,
                "progress": _progress_for_status(j.status),
                "error_message": j.last_error,
                "attempts": j.attempts,
                "payload": j.payload_json,
                "result": j.result_json,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in rows
        ]

        # Image generation: show one row per user request (batch), not each child render.
        # Child jobs still hold the real per-image cost for analytics.
        image_rows = (
            await self._session.execute(
                select(ImageJob)
                .where(
                    ImageJob.organization_id == org_id,
                )
                .order_by(ImageJob.created_at.desc())
                .limit(limit * 3)
            )
        ).scalars().all()
        for img in image_rows:
            meta = img.generation_metadata_json or {}
            is_batch = bool(meta.get("batch") or meta.get("async"))
            is_child = "variant_index" in meta and not is_batch
            if is_child:
                continue
            if not is_batch and not img.provider and img.status not in {
                "pending",
                "running",
                "queued",
                "generating",
            }:
                continue
            items.append(
                {
                    "id": str(img.id),
                    "type": "image_generate",
                    "status": img.status,
                    "progress": _progress_for_status(img.status),
                    "error_message": img.error_message,
                    "attempts": img.retry_count or 0,
                    "payload": {
                        "draft_id": str(img.draft_id) if img.draft_id else None,
                        "provider": img.provider,
                        "model": img.model,
                        "cost_estimate": img.cost_estimate
                        if img.cost_estimate is not None
                        else meta.get("total_cost_estimate"),
                        "requested_count": meta.get("requested_count")
                        or meta.get("result_count")
                        or 1,
                        "metadata": meta,
                    },
                    "result": {
                        "quality_score": img.quality_score,
                        "latency_ms": img.latency_ms,
                    },
                    "created_at": img.created_at.isoformat() if img.created_at else None,
                }
            )

        items.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return items[:limit]


class GetJobUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, Any]:
        job = await self._session.get(Job, job_id)
        if job is not None and job.organization_id == org_id:
            return {
                "id": str(job.id),
                "type": job.job_type,
                "status": job.status,
                "progress": _progress_for_status(job.status),
                "error_message": job.last_error,
                "attempts": job.attempts,
                "payload": job.payload_json,
                "result": job.result_json,
            }
        img = await self._session.get(ImageJob, job_id)
        if img is None or img.organization_id != org_id:
            raise NotFoundError("Job", str(job_id))
        meta = img.generation_metadata_json or {}
        return {
            "id": str(img.id),
            "type": "image_generate",
            "status": img.status,
            "progress": _progress_for_status(img.status),
            "error_message": img.error_message,
            "attempts": img.retry_count or 0,
            "payload": {
                "draft_id": str(img.draft_id) if img.draft_id else None,
                "provider": img.provider,
                "model": img.model,
                "cost_estimate": img.cost_estimate,
                "metadata": meta,
            },
            "result": {
                "quality_score": img.quality_score,
                "latency_ms": img.latency_ms,
            },
        }


class ExportDiagnosticsUseCase:
    """Bundle recent job history + a server log tail + environment info into a
    zip the client can send to their agency when something goes wrong.

    Deliberately never includes settings/env vars/API keys — only job records
    (already org-scoped, same data the Jobs page shows) and the on-disk log
    file, which exists independent of whether the app is currently running.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID) -> tuple[bytes, str]:
        from app.modules.organization.application.use_cases import GetOrganizationUseCase
        from app.modules.organization.infrastructure.repositories import (
            PgOrganizationRepository,
        )

        org = await GetOrganizationUseCase(PgOrganizationRepository(self._session)).execute(
            org_id
        )
        jobs = await ListJobsUseCase(self._session).execute(org_id, limit=200)

        now = datetime.now(timezone.utc)
        environment = {
            "organization_id": str(org_id),
            "organization_name": org.get("name"),
            "exported_at": now.isoformat(),
            "python_version": sys.version,
            "git_commit": _git_commit(),
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("jobs.json", json.dumps(jobs, indent=2, default=str))
            zf.writestr("environment.json", json.dumps(environment, indent=2))
            zf.writestr("recent_logs.txt", _read_log_tail())
        buf.seek(0)

        slug = str(org.get("slug") or "org")
        filename = f"diagnostics-{slug}-{now.strftime('%Y%m%d-%H%M%S')}.zip"
        return buf.getvalue(), filename


def _git_commit() -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # noqa: BLE001 — best-effort only
        pass
    return None


# Settings whose values must never leave the machine in a diagnostics bundle.
_SECRET_SETTINGS = (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PERPLEXITY_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_API_KEY",
    "VLLM_API_KEY",
    "GROK_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_SPEECH_KEY",
    "AZURE_TRANSLATOR_KEY",
    "NEWSDATA_API_KEY",
    "GNEWS_API_KEY",
    "GUARDIAN_API_KEY",
    "CURRENTS_API_KEY",
    "JWT_SECRET_KEY",
    "JWT_REFRESH_SECRET_KEY",
    "DATABASE_URL",
)

# Provider SDKs log full request URLs, which for Google puts the API key in the
# query string (…:generateContent?key=AIza…). Catches keys we don't hold in
# settings too, e.g. a per-source key stored on a news source.
_URL_SECRET_RE = re.compile(
    r"([?&](?:key|api_key|apikey|access_token|token)=)[^&\s\"'\\]+", re.IGNORECASE
)


def _redact_secrets(text: str) -> str:
    """Strip credentials from log text before it is bundled for sending.

    This bundle is meant to be emailed to the agency, so anything secret in it
    is disclosed. Redacts known settings values by exact match, then any
    credential-shaped query parameter.
    """
    from app.core.config import get_settings

    settings = get_settings()
    for name in _SECRET_SETTINGS:
        value = str(getattr(settings, name, "") or "")
        # Short values would match far too much unrelated text.
        if len(value) >= 8:
            text = text.replace(value, f"<redacted:{name}>")
    return _URL_SECRET_RE.sub(r"\1<redacted>", text)


def _read_log_tail(max_lines: int = 5000, max_bytes: int = 2 * 1024 * 1024) -> str:
    from app.core.config import get_settings

    log_path = Path(get_settings().LOG_DIR) / "app.log"
    if not log_path.is_file():
        return "(no log file found — the app may not have written to disk yet)"
    try:
        data = log_path.read_bytes()
        if len(data) > max_bytes:
            data = data[-max_bytes:]
        lines = data.decode("utf-8", errors="replace").splitlines()[-max_lines:]
        return _redact_secrets("\n".join(lines))
    except OSError as exc:
        return f"(could not read log file: {exc})"


def _progress_for_status(status: str) -> int:
    mapping = {
        "pending": 0,
        "queued": 0,
        "running": 50,
        "generating": 50,
        "retrying": 40,
        "completed": 100,
        "complete": 100,
        "failed": 100,
    }
    return mapping.get(status, 0)
