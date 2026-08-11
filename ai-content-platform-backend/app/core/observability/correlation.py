"""Correlation ID and OpenTelemetry-ready observability helpers."""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_organization_id: ContextVar[str] = ContextVar("organization_id", default="")


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(value: str) -> Token[str]:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[str]) -> None:
    _correlation_id.reset(token)


def ensure_correlation_id(explicit: str | None = None) -> str:
    """Return explicit id, existing context, or a newly bound UUID."""
    if explicit:
        set_correlation_id(explicit)
        return explicit
    current = _correlation_id.get()
    if current:
        return current
    generated = str(uuid.uuid4())
    set_correlation_id(generated)
    return generated


def get_organization_id() -> str:
    return _organization_id.get()


def set_organization_id(value: str) -> Token[str]:
    return _organization_id.set(value)


def reset_organization_id(token: Token[str]) -> None:
    _organization_id.reset(token)


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Stable attributes for structured logs and future OTel spans."""

    correlation_id: str
    organization_id: str = ""
    module: str = ""
    operation: str = ""

    def as_log_extra(self, **more: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "correlation_id": self.correlation_id,
            "app_module": self.module,
            "operation": self.operation,
        }
        if self.organization_id:
            data["organization_id"] = self.organization_id
        data.update({k: v for k, v in more.items() if v is not None})
        return data


@contextmanager
def traced_operation(
    module: str,
    operation: str,
    *,
    organization_id: str | None = None,
) -> Iterator[TraceContext]:
    """Context manager that records duration/outcome fields for OTel-ready logs."""
    from app.core.logging import get_logger

    logger = get_logger(f"{module}.{operation}")
    ctx = TraceContext(
        correlation_id=ensure_correlation_id(),
        organization_id=organization_id or get_organization_id(),
        module=module,
        operation=operation,
    )
    start = time.perf_counter()
    outcome = "success"
    try:
        yield ctx
    except Exception:
        outcome = "failure"
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            f"{module}.{operation}",
            extra=ctx.as_log_extra(duration_ms=duration_ms, outcome=outcome),
        )
