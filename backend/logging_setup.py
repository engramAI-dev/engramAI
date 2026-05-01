"""Structured JSON logging — production observability for Engram backend.

All log records emit one JSON line to stdout, ready for Better Stack
via backend host's log drain. The `request_id` contextvar is set per-request
by `api.request_id_middleware` and propagates across `await` boundaries,
so every log line emitted during a request carries the same correlation ID.

Usage:
    logger.info("ingest_started", extra={"repo": repo, "user_id": user_id})

The reserved logging fields (level, logger, msg, etc.) are emitted
automatically; anything else from `extra=` lands alongside as a top-level
JSON field.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

# Set per-request; "-" sentinel for non-request logs (startup, Celery boot, etc.).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# LogRecord built-ins we already emit ourselves or don't want to leak.
_RESERVED_FIELDS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})


class JSONFormatter(logging.Formatter):
    """One JSON line per record. Includes request_id and any `extra=` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Wire root logger to stdout with JSON output. Idempotent."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Suppress uvicorn's text access log — our usage middleware emits a richer
    # structured equivalent. Keep uvicorn.error so startup/shutdown still log.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


def new_request_id() -> str:
    """Generate a fresh request ID for inbound requests without an X-Request-ID."""
    return uuid.uuid4().hex
