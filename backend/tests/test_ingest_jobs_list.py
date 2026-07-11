"""Tests for `GET /api/ingest/jobs` — hermetic, fakes the DB session."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import ingest
from api.workspace import get_active_team_id
from models.database import get_session

USER_ID = "00000000-0000-0000-0000-000000000001"


def _job(
    *,
    status: str,
    source: str = "github",
    user_id: str = USER_ID,
    minutes_ago: int = 0,
    source_url: str = "https://github.com/oct/repo",
    error: str | None = None,
) -> Any:
    """Build a fake `IngestJob` row with the attributes the route reads."""
    ts = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_ago)
    obj = type("Row", (), {})()
    obj.id = uuid.uuid4()
    obj.user_id = uuid.UUID(user_id)
    obj.source = source
    obj.source_url = source_url
    obj.status = status
    obj.progress = 0.0
    obj.documents_indexed = 0
    obj.total_documents = None
    obj.error_message = error
    obj.created_at = ts
    obj.updated_at = ts
    return obj


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """Applies the route's filters in-memory and returns matching rows."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, stmt: Any) -> _FakeResult:
        sql = str(stmt).lower()
        rows = list(self._rows)
        if "ingest_jobs.status !=" in sql or "status !=" in sql:
            rows = [r for r in rows if r.status != "complete"]
        if "ingest_jobs.user_id =" in sql or "user_id =" in sql:
            rows = [r for r in rows if str(r.user_id) == USER_ID]
        if "ingest_jobs.source =" in sql:
            for token in ("'github'", "'notion'"):
                if token in sql:
                    src = token.strip("'")
                    rows = [r for r in rows if r.source == src]
                    break
        rows.sort(key=lambda r: r.updated_at, reverse=True)
        return _FakeResult(rows[:50])


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(ingest.router, prefix="/api/ingest")
    app.dependency_overrides[get_active_team_id] = lambda: uuid.UUID(
        "00000000-0000-0000-0000-0000000000bb"
    )
    return app


def _override_session(app: FastAPI, rows: list[Any]) -> None:
    async def _gen() -> AsyncIterator[_FakeSession]:
        yield _FakeSession(rows)

    app.dependency_overrides[get_session] = _gen


@pytest.fixture
def auth_headers(mint_jwt: Any) -> dict[str, str]:
    token = mint_jwt(
        {"sub": USER_ID, "github_username": "alice", "exp": int(time.time()) + 60}
    )
    return {"Authorization": f"Bearer {token}"}


def test_empty_list(app: FastAPI, auth_headers: dict[str, str]) -> None:
    _override_session(app, [])
    with TestClient(app) as client:
        res = client.get("/api/ingest/jobs", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_filters_complete_status(app: FastAPI, auth_headers: dict[str, str]) -> None:
    rows = [
        _job(status="processing", minutes_ago=1),
        _job(status="complete", minutes_ago=2),
        _job(status="failed", minutes_ago=3, error="boom"),
        _job(status="queued", minutes_ago=4),
    ]
    _override_session(app, rows)
    with TestClient(app) as client:
        res = client.get("/api/ingest/jobs", headers=auth_headers)
    assert res.status_code == 200
    statuses = [r["status"] for r in res.json()]
    assert "complete" not in statuses
    assert set(statuses) == {"processing", "failed", "queued"}


def test_scoped_to_caller(app: FastAPI, auth_headers: dict[str, str]) -> None:
    other_user = "00000000-0000-0000-0000-000000000099"
    rows = [
        _job(status="processing", user_id=USER_ID, minutes_ago=1),
        _job(status="processing", user_id=other_user, minutes_ago=1),
    ]
    _override_session(app, rows)
    with TestClient(app) as client:
        res = client.get("/api/ingest/jobs", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1


def test_ordered_by_updated_at_desc(
    app: FastAPI, auth_headers: dict[str, str]
) -> None:
    rows = [
        _job(status="queued", minutes_ago=10, source_url="oldest"),
        _job(status="queued", minutes_ago=1, source_url="newest"),
        _job(status="queued", minutes_ago=5, source_url="middle"),
    ]
    _override_session(app, rows)
    with TestClient(app) as client:
        res = client.get("/api/ingest/jobs", headers=auth_headers)
    urls = [r["source_url"] for r in res.json()]
    assert urls == ["newest", "middle", "oldest"]
