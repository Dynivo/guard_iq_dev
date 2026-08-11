"""Gallery selection for draft images — one displayable asset per generation job."""

from __future__ import annotations

from typing import Protocol, TypeVar


class _MediaLike(Protocol):
    object_key: str


T = TypeVar("T", bound=_MediaLike)


def job_id_and_role_from_object_key(object_key: str) -> tuple[str | None, str | None]:
    """Parse ``{org}/images/{job_id}/{role}.png`` → (job_id, role)."""
    parts = (object_key or "").strip("/").split("/")
    if len(parts) < 4 or parts[1] != "images":
        return None, None
    job_id = parts[2]
    role = parts[3].rsplit(".", 1)[0]
    return job_id or None, role or None


def _role_rank(role: str | None) -> int:
    """Higher is preferred for the gallery."""
    if role == "optimized":
        return 3
    if role == "original":
        return 1
    if role == "thumbnail":
        return 0
    return 2


def select_gallery_media(rows: list[T]) -> list[T]:
    """Collapse original+optimized (same job) to a single gallery item.

    Prefers ``optimized``. Rows without a parseable job key are kept as-is.
    Preserves newest-first order of the chosen representatives.
    """
    by_job: dict[str, T] = {}
    orphans: list[T] = []
    job_order: list[str] = []

    for row in rows:
        job_id, role = job_id_and_role_from_object_key(row.object_key)
        if not job_id:
            orphans.append(row)
            continue
        existing = by_job.get(job_id)
        if existing is None:
            by_job[job_id] = row
            job_order.append(job_id)
            continue
        _, existing_role = job_id_and_role_from_object_key(existing.object_key)
        if _role_rank(role) > _role_rank(existing_role):
            by_job[job_id] = row

    selected = [by_job[jid] for jid in job_order]
    return selected + orphans


def media_belongs_to_jobs(object_key: str, job_ids: set[str]) -> bool:
    job_id, _ = job_id_and_role_from_object_key(object_key)
    return bool(job_id and job_id in job_ids)
