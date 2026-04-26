"""B6b — `/outputs/*` route tests.

Hermetic: swaps `get_session` + `get_current_user` + `generate_output` via
`dependency_overrides` / `monkeypatch`. No DB.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware import CurrentUser, get_current_user
from api.routes import outputs
from models.database import get_session
from models.output import Output

USER_ID = "00000000-0000-0000-0000-000000000001"
MESSAGE_ID = "00000000-0000-0000-0000-0000000000aa"
CONV_ID = "00000000-0000-0000-0000-0000000000bb"


def _make_output(**overrides: Any) -> Output:
    o = Output(
        user_id=uuid.UUID(USER_ID),
        message_id=uuid.UUID(MESSAGE_ID),
        conversation_id=uuid.UUID(CONV_ID),
        type="code_snippet",
        title="Hello world",
        content="print('hi')",
        output_metadata={
            "language": "python",
            "file_path_suggestion": "hello.py",
            "source_message_id": MESSAGE_ID,
            "source_conversation_id": CONV_ID,
        },
    )
    o.id = overrides.get("id", uuid.uuid4())
    o.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    for k, v in overrides.items():
        if k not in {"id", "created_at"}:
            setattr(o, k, v)
    return o


class _FakeResult:
    def __init__(self, scalar: Any = None, scalar_one: Any = None, rows: list[Any] | None = None) -> None:
        self._scalar = scalar
        self._scalar_one = scalar_one
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalar_one(self) -> Any:
        return self._scalar_one

    def scalars(self) -> Any:
        rows = self._rows

        class _S:
            def all(self) -> list[Any]:
                return rows

        return _S()


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed: list[Any] = []
        self._scalar: Any = None  # for GET /{id}
        self._list_rows: list[Any] = []  # for GET ""
        self._list_total: int = 0
        self.executed: list[Any] = []

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        self.refreshed.append(obj)

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        compiled = str(stmt).lower()
        if "count(" in compiled:
            return _FakeResult(scalar_one=self._list_total)
        if "limit" in compiled or "offset" in compiled:
            return _FakeResult(rows=self._list_rows)
        return _FakeResult(scalar=self._scalar)


@pytest.fixture
def fake_session() -> _FakeSession:
    return _FakeSession()


@pytest.fixture
def app(fake_session: _FakeSession) -> FastAPI:
    app = FastAPI()
    app.include_router(outputs.router, prefix="/api/outputs")

    async def _session_override() -> AsyncIterator[_FakeSession]:
        yield fake_session

    app.dependency_overrides[get_session] = _session_override
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(mint_jwt: Any) -> dict[str, str]:
    token = mint_jwt(
        {"sub": USER_ID, "github_username": "alice", "exp": int(time.time()) + 60}
    )
    return {"Authorization": f"Bearer {token}"}


def test_post_generate_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/api/outputs/generate",
        json={"message_id": MESSAGE_ID, "output_type": "code_snippet"},
    )
    assert r.status_code == 401


def test_post_generate_validates_output_type(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/api/outputs/generate",
        json={"message_id": MESSAGE_ID, "output_type": "bogus"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_post_generate_returns_400_on_value_error(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(**_: Any) -> Output:
        raise ValueError("response_text is empty")

    monkeypatch.setattr(outputs, "generate_output", _raise)
    r = client.post(
        "/api/outputs/generate",
        json={"message_id": MESSAGE_ID, "output_type": "summary"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_post_generate_returns_full_shape_on_success(
    client: TestClient,
    auth_headers: dict[str, str],
    fake_session: _FakeSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _make_output()

    async def _ok(**_: Any) -> Output:
        return created

    monkeypatch.setattr(outputs, "generate_output", _ok)
    r = client.post(
        "/api/outputs/generate",
        json={"message_id": MESSAGE_ID, "output_type": "code_snippet"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == str(created.id)
    assert body["type"] == "code_snippet"
    assert body["title"] == "Hello world"
    assert body["content"] == "print('hi')"
    assert body["metadata"] == {
        "language": "python",
        "file_path_suggestion": "hello.py",
        "source_message_id": MESSAGE_ID,
        "source_conversation_id": CONV_ID,
    }
    assert fake_session.committed is True


def test_get_list_requires_auth(client: TestClient) -> None:
    r = client.get("/api/outputs")
    assert r.status_code == 401


def test_get_list_returns_empty_when_no_outputs(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    fake_session._list_rows = []
    fake_session._list_total = 0
    r = client.get("/api/outputs", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"outputs": [], "total": 0, "page": 1}


def test_get_list_returns_paginated_shape(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    rows = [_make_output(content="A" * 250), _make_output(content="short")]
    fake_session._list_rows = rows
    fake_session._list_total = 23
    r = client.get(
        "/api/outputs", params={"page": 2, "limit": 5}, headers=auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 23
    assert body["page"] == 2
    assert len(body["outputs"]) == 2
    # Preview is first 200 chars of content.
    assert body["outputs"][0]["preview"] == "A" * 200
    assert body["outputs"][1]["preview"] == "short"
    # List items omit content + metadata; only summary fields.
    assert "content" not in body["outputs"][0]
    assert "metadata" not in body["outputs"][0]


def test_get_list_validates_limit_upper_bound(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/api/outputs", params={"limit": 999}, headers=auth_headers)
    assert r.status_code == 422


def test_get_list_validates_page_lower_bound(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/api/outputs", params={"page": 0}, headers=auth_headers)
    assert r.status_code == 422


def test_get_list_validates_type_enum(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/api/outputs", params={"type": "bogus"}, headers=auth_headers)
    assert r.status_code == 422


def test_get_list_passes_type_filter_into_query(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    fake_session._list_rows = []
    fake_session._list_total = 0
    r = client.get(
        "/api/outputs", params={"type": "summary"}, headers=auth_headers
    )
    assert r.status_code == 200
    # Both queries (count + list) should mention the type filter.
    assert any("type" in str(s).lower() for s in fake_session.executed)


def test_get_by_id_requires_auth(client: TestClient) -> None:
    r = client.get(f"/api/outputs/{uuid.uuid4()}")
    assert r.status_code == 401


def test_get_by_id_returns_404_when_missing(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    fake_session._scalar = None
    r = client.get(f"/api/outputs/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


def test_get_by_id_returns_full_output(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    row = _make_output()
    fake_session._scalar = row
    r = client.get(f"/api/outputs/{row.id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(row.id)
    assert body["title"] == "Hello world"
    assert body["metadata"]["language"] == "python"


def test_get_by_id_rejects_malformed_uuid(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/api/outputs/not-a-uuid", headers=auth_headers)
    assert r.status_code == 422


def test_get_by_id_bypasses_auth_with_override(
    app: FastAPI, fake_session: _FakeSession
) -> None:
    # Sanity check: dependency override pathway works end-to-end.
    async def _user() -> CurrentUser:
        return CurrentUser(id=USER_ID, github_username="bob")

    app.dependency_overrides[get_current_user] = _user
    try:
        row = _make_output()
        fake_session._scalar = row
        with TestClient(app) as c:
            r = c.get(f"/api/outputs/{row.id}")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
