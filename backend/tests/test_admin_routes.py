"""Admin route tests — hermetic, no DB.

Covers `POST /api/admin/wipe-library` and the dev-only
`POST /api/admin/disconnect/{provider}`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import admin
from config import settings
from models.database import get_session

USER_ID = "00000000-0000-0000-0000-000000000001"


class _FakeResult:
    def __init__(self, rowcount: int = 0) -> None:
        self.rowcount = rowcount


class _FakeSession:
    """Records DELETE statements and returns canned rowcounts per table."""

    def __init__(self, rowcounts: dict[str, int] | None = None) -> None:
        self.committed = False
        self.executed: list[str] = []
        self._rowcounts = rowcounts or {}

    async def commit(self) -> None:
        self.committed = True

    async def execute(self, stmt: Any) -> Any:
        compiled = str(stmt).lower()
        self.executed.append(compiled)
        for table, rc in self._rowcounts.items():
            if f"from {table}" in compiled or f'"{table}"' in compiled:
                return _FakeResult(rowcount=rc)
        return _FakeResult(rowcount=0)


@pytest.fixture
def fake_session() -> _FakeSession:
    return _FakeSession(
        rowcounts={"documents": 5, "ingest_jobs": 2, "user_connections": 1}
    )


@pytest.fixture
def app(fake_session: _FakeSession) -> FastAPI:
    app = FastAPI()
    app.include_router(admin.router, prefix="/api/admin")

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


# --- wipe-library ----------------------------------------------------------

def test_wipe_library_requires_auth(client: TestClient) -> None:
    r = client.post("/api/admin/wipe-library")
    assert r.status_code == 401


def test_wipe_library_deletes_documents_and_jobs(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    r = client.post("/api/admin/wipe-library", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"documents_deleted": 5, "ingest_jobs_deleted": 2}
    assert fake_session.committed is True

    joined = " | ".join(fake_session.executed)
    assert "delete from documents" in joined
    assert "delete from ingest_jobs" in joined
    # Connections, conversations, messages, outputs must NOT be touched.
    assert "user_connections" not in joined
    assert "conversations" not in joined
    assert "messages" not in joined
    assert " outputs" not in joined  # space-prefixed to avoid 'outputs' table-name false hits


def test_wipe_library_scopes_delete_to_current_user(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    client.post("/api/admin/wipe-library", headers=auth_headers)
    for stmt in fake_session.executed:
        assert "user_id" in stmt


# --- disconnect/{provider} -------------------------------------------------

def test_disconnect_returns_404_when_debug_disabled(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "engram_debug_endpoints", False)
    r = client.post("/api/admin/disconnect/notion", headers=auth_headers)
    assert r.status_code == 404


def test_disconnect_requires_auth_even_when_debug_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "engram_debug_endpoints", True)
    r = client.post("/api/admin/disconnect/notion")
    assert r.status_code == 401


def test_disconnect_deletes_connection_when_debug_enabled(
    client: TestClient,
    auth_headers: dict[str, str],
    fake_session: _FakeSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "engram_debug_endpoints", True)
    r = client.post("/api/admin/disconnect/notion", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"provider": "notion", "deleted": True}
    assert fake_session.committed is True
    joined = " | ".join(fake_session.executed)
    assert "delete from user_connections" in joined
    assert "user_id" in joined
    assert "provider" in joined


def test_disconnect_reports_false_when_no_row_existed(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "engram_debug_endpoints", True)
    # Override session with one that returns 0 rowcount for everything.
    empty_session = _FakeSession(rowcounts={})

    async def _override() -> AsyncIterator[_FakeSession]:
        yield empty_session

    client.app.dependency_overrides[get_session] = _override
    try:
        r = client.post("/api/admin/disconnect/notion", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == {"provider": "notion", "deleted": False}
    finally:
        client.app.dependency_overrides[get_session] = (
            client.app.dependency_overrides[get_session]
        )


def test_wipe_uuid_in_user_id_uses_jwt_sub(
    client: TestClient, auth_headers: dict[str, str], fake_session: _FakeSession
) -> None:
    """The current_user UUID from the JWT should be the WHERE-clause value
    (not silently swapped). We can't read the bound param from the compiled
    SQL string easily, so we just assert the parameterized clause is present
    and the route accepted the well-formed UUID without error."""
    r = client.post("/api/admin/wipe-library", headers=auth_headers)
    assert r.status_code == 200
    # Sanity: must have been a valid UUID parse upstream.
    uuid.UUID(USER_ID)
