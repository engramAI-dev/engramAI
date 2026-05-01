"""Lane5/D2 — request-ID middleware tests.

Drive a minimal FastAPI app via TestClient; verify the contextvar is
set during the request and the response echoes the ID back.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.request_id_middleware import request_id_middleware
from logging_setup import request_id_var


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.middleware("http")(request_id_middleware)

    @a.get("/peek")
    async def peek(request: Request) -> dict[str, str]:
        # Read the contextvar inside the request scope to confirm it was set.
        return {"rid": request_id_var.get()}

    return a


def test_generates_uuid_when_no_header(app: FastAPI) -> None:
    client = TestClient(app)
    response = client.get("/peek")
    assert response.status_code == 200
    rid_in_body = response.json()["rid"]
    rid_in_header = response.headers["x-request-id"]
    assert rid_in_body == rid_in_header
    assert rid_in_body != "-"
    assert len(rid_in_body) == 32  # uuid4 hex


def test_honors_inbound_header(app: FastAPI) -> None:
    client = TestClient(app)
    response = client.get("/peek", headers={"X-Request-ID": "caller-supplied-123"})
    assert response.json()["rid"] == "caller-supplied-123"
    assert response.headers["x-request-id"] == "caller-supplied-123"


def test_resets_contextvar_after_request(app: FastAPI) -> None:
    client = TestClient(app)
    client.get("/peek", headers={"X-Request-ID": "first"})
    # After the request returns, the contextvar should be back to the sentinel.
    assert request_id_var.get() == "-"
