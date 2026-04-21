"""B13 — usage tracking middleware tests.

Hermetic: mount middleware on a minimal FastAPI app, drive with TestClient,
capture `engram.usage` logger output.
"""

import json
import logging
import time
from typing import Any

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from api.middleware import CurrentUser, get_current_user
from api.usage_middleware import usage_tracking_middleware


@pytest.fixture
def app_with_middleware() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(usage_tracking_middleware)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    @app.get("/me")
    async def me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"id": user.id}

    @app.post("/chat")
    async def chat(request: Request) -> dict[str, str]:
        request.state.usage = {"input_tokens": 42, "output_tokens": 7}
        return {"ok": "yes"}

    return app


def _captured(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    records = [r for r in caplog.records if r.name == "engram.usage"]
    assert records, "expected at least one engram.usage log record"
    return json.loads(records[-1].message)


def test_logs_basic_request(
    app_with_middleware: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="engram.usage")
    client = TestClient(app_with_middleware)
    response = client.get("/ok")
    assert response.status_code == 200

    record = _captured(caplog)
    assert record["event"] == "http_request"
    assert record["path"] == "/ok"
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert record["user_id"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["duration_ms"] >= 0


def test_logs_error_status(
    app_with_middleware: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="engram.usage")
    client = TestClient(app_with_middleware, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500

    record = _captured(caplog)
    assert record["path"] == "/boom"
    assert record["status"] == 500


def test_captures_user_id_when_authenticated(
    app_with_middleware: FastAPI,
    caplog: pytest.LogCaptureFixture,
    mint_jwt: Any,
) -> None:
    caplog.set_level(logging.INFO, logger="engram.usage")
    token = mint_jwt({"sub": "u42", "github_username": "alice", "exp": int(time.time()) + 60})
    client = TestClient(app_with_middleware)
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    record = _captured(caplog)
    assert record["user_id"] == "u42"


def test_captures_usage_counts_when_route_sets_them(
    app_with_middleware: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="engram.usage")
    client = TestClient(app_with_middleware)
    response = client.post("/chat")
    assert response.status_code == 200

    record = _captured(caplog)
    assert record["input_tokens"] == 42
    assert record["output_tokens"] == 7


def test_unauthenticated_401_still_logged(
    app_with_middleware: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="engram.usage")
    client = TestClient(app_with_middleware)
    response = client.get("/me")
    assert response.status_code == 401

    record = _captured(caplog)
    assert record["status"] == 401
    assert record["user_id"] is None
