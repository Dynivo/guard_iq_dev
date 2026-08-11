"""Structured JSON logging configuration with OTel-ready correlation fields."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

import orjson

from app.core.observability.correlation import get_correlation_id, get_organization_id


class StructuredFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        organization_id = getattr(record, "organization_id", None) or get_organization_id()
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id or None,
        }
        if organization_id:
            log_entry["organization_id"] = organization_id
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        reserved = set(logging.LogRecord("", 0, "", 0, None, None, None).__dict__)
        reserved.update({"message", "msg", "args", "correlation_id", "organization_id"})
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in reserved and v is not None
        }
        # Promote OTel-ready fields to top level when present.
        # app_module avoids clashing with LogRecord.module; emit as "module" in JSON.
        if "app_module" in extras:
            log_entry["module"] = extras.pop("app_module")
        for key in ("operation", "duration_ms", "outcome", "event_type", "event_id"):
            if key in extras:
                log_entry[key] = extras.pop(key)
        if extras:
            log_entry["extra"] = extras
        return orjson.dumps(log_entry).decode("utf-8")


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with structured formatting."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a module."""
    return logging.getLogger(name)
