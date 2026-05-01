"""Lane5/D2 — JSONFormatter + setup_logging tests.

Hermetic: format LogRecords directly, no I/O.
"""

import json
import logging

from logging_setup import (
    JSONFormatter,
    new_request_id,
    request_id_var,
    setup_logging,
)


def _record(
    msg: str = "msg",
    level: int = logging.INFO,
    extra: dict | None = None,
) -> logging.LogRecord:
    """Build a LogRecord the way the logging machinery does, including extras."""
    record = logging.LogRecord(
        name="test",
        level=level,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=None,
        exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


def test_json_formatter_emits_standard_fields() -> None:
    out = JSONFormatter().format(_record(msg="hello"))
    payload = json.loads(out)
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert "ts" in payload
    assert payload["request_id"] == "-"  # default sentinel


def test_json_formatter_includes_request_id_from_contextvar() -> None:
    token = request_id_var.set("rid-abc")
    try:
        out = JSONFormatter().format(_record(msg="m"))
        payload = json.loads(out)
        assert payload["request_id"] == "rid-abc"
    finally:
        request_id_var.reset(token)


def test_json_formatter_passes_extras_through() -> None:
    out = JSONFormatter().format(
        _record(msg="m", extra={"path": "/x", "duration_ms": 12.3})
    )
    payload = json.loads(out)
    assert payload["path"] == "/x"
    assert payload["duration_ms"] == 12.3


def test_json_formatter_does_not_leak_internal_fields() -> None:
    out = JSONFormatter().format(_record(msg="m"))
    payload = json.loads(out)
    # Internal LogRecord fields should be filtered out.
    assert "args" not in payload
    assert "pathname" not in payload
    assert "filename" not in payload
    assert "module" not in payload


def test_json_formatter_renders_exception_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record = _record(msg="m", level=logging.ERROR)
        record.exc_info = sys.exc_info()
        out = JSONFormatter().format(record)
        payload = json.loads(out)
        assert "exc_info" in payload
        assert "ValueError" in payload["exc_info"]


def test_setup_logging_replaces_root_handlers() -> None:
    setup_logging(level="DEBUG")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    assert root.level == logging.DEBUG


def test_setup_logging_silences_uvicorn_access() -> None:
    setup_logging()
    access = logging.getLogger("uvicorn.access")
    assert access.handlers == []
    assert access.propagate is False


def test_new_request_id_unique_and_hex() -> None:
    a = new_request_id()
    b = new_request_id()
    assert a != b
    assert len(a) == 32
    int(a, 16)  # parses as hex
