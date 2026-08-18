"""Async SQLAlchemy 2.0 engine and session factory.

Automatically selects NullPool for SQLite (test), QueuePool for Postgres.
Exposes `get_async_session` as a FastAPI dependency generator.
Enables TLS for remote Postgres (e.g. AWS RDS) — required by typical pg_hba rules.
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_RDS_CA = Path(__file__).resolve().parents[3] / "certs" / "rds-global-bundle.pem"


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


def _needs_ssl(database_url: str) -> bool:
    """RDS and most cloud Postgres reject non-TLS clients."""
    settings = get_settings()
    flag = (getattr(settings, "DATABASE_SSL", "") or "").strip().lower()
    if flag in {"1", "true", "yes", "require", "require-insecure"}:
        return True
    if flag in {"0", "false", "no", "disable"}:
        return False
    raw = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    host = (urlparse(raw).hostname or "").lower()
    return host not in {"", "localhost", "127.0.0.1", "::1"}


def _ssl_context() -> ssl.SSLContext:
    """Build asyncpg SSL context for AWS RDS / cloud Postgres."""
    settings = get_settings()
    ca = (getattr(settings, "DATABASE_SSL_CA", "") or "").strip()
    flag = (getattr(settings, "DATABASE_SSL", "") or "").strip().lower()

    if not ca and _DEFAULT_RDS_CA.is_file():
        ca = str(_DEFAULT_RDS_CA)

    if ca:
        logger.info("Postgres TLS using CA bundle: %s", ca)
        return ssl.create_default_context(cafile=ca)

    if flag == "require-insecure":
        if settings.APP_ENV.lower() == "production":
            raise RuntimeError(
                "DATABASE_SSL=require-insecure is not allowed in production; "
                "configure DATABASE_SSL_CA instead"
            )
        logger.warning("Postgres TLS certificate verification disabled for development")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    # Use the operating system trust store when no application-specific CA is
    # configured. Connection failure is safer than silently accepting an
    # unverified database certificate.
    return ssl.create_default_context()


def engine_connect_args(database_url: str) -> dict[str, Any]:
    """connect_args for asyncpg — SSL context when connecting to remote hosts."""
    if database_url.startswith("sqlite"):
        return {}
    if _needs_ssl(database_url):
        return {"ssl": _ssl_context()}
    return {}


def _build_engine() -> Any:
    settings = get_settings()
    pool_class = NullPool if settings.is_sqlite else None
    kwargs: dict = {
        "echo": settings.APP_DEBUG,
        "connect_args": engine_connect_args(settings.DATABASE_URL),
    }
    if pool_class is not None:
        kwargs["poolclass"] = pool_class
    return create_async_engine(settings.DATABASE_URL, **kwargs)


async_engine = _build_engine()
async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async session and commits on success."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
