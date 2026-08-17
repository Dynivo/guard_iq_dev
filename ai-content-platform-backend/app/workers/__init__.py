"""Dramatiq worker actors — imported here so `dramatiq app.workers` discovers them."""

from app.workers.broker import ensure_broker  # noqa: F401
from app.workers.draft_generation import (  # noqa: F401
    run_fill_educational_task,
    run_generate_draft_task,
    run_regenerate_draft_task,
    run_regenerate_plan_task,
)
from app.workers.ingest import run_ingest_task  # noqa: F401
