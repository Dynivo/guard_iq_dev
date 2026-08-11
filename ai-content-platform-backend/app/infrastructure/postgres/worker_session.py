"""Per-task async SQLAlchemy engines for Dramatiq / short-lived event loops.

Dramatiq runs actors in OS threads and each task calls ``asyncio.run()``,
which creates a *new* event loop. Sharing the process-global ``async_engine``
across those loops causes asyncpg errors:

    InterfaceError: cannot perform operation: another operation is in progress

Always create a fresh NullPool engine for the current loop and dispose it
when the task finishes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.infrastructure.postgres.session import engine_connect_args


def create_task_engine() -> AsyncEngine:
    """Build an async engine safe for a single asyncio.run() invocation."""
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        connect_args=engine_connect_args(settings.DATABASE_URL),
    )


@asynccontextmanager
async def worker_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield a sessionmaker bound to a loop-local engine; dispose on exit."""
    engine = create_task_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()
