"""Jobs module ports — job tracking and event logging."""

from __future__ import annotations

import uuid
from typing import Protocol


class JobRepository(Protocol):
    """Port for background job persistence."""

    async def create(self, job: dict) -> uuid.UUID: ...

    async def get_by_id(self, job_id: uuid.UUID) -> dict | None: ...

    async def update_status(self, job_id: uuid.UUID, status: str, error: str | None = None) -> None: ...

    async def list_by_org(self, org_id: uuid.UUID, status: str | None = None) -> list[dict]: ...

    async def add_event(self, job_id: uuid.UUID, event_type: str, message: str | None = None) -> None: ...
