"""Dramatiq broker configuration.

Lazily initializes the Redis broker so importing this module in inline
mode (no Redis) doesn't fail.  The broker is only used when
JOB_BACKEND=dramatiq.
"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_broker_initialized = False


def ensure_broker() -> None:
    """Set up the Dramatiq Redis broker once. No-op on subsequent calls."""
    global _broker_initialized
    if _broker_initialized:
        return

    settings = get_settings()
    if settings.JOB_BACKEND != "dramatiq":
        logger.info("JOB_BACKEND=%s — skipping Dramatiq broker init", settings.JOB_BACKEND)
        return

    broker = RedisBroker(url=settings.REDIS_URL)
    dramatiq.set_broker(broker)
    _broker_initialized = True
    logger.info("Dramatiq broker initialized: %s", settings.REDIS_URL)
