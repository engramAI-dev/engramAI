"""Provider route tests — hermetic, no DB.

Regression coverage for the F2/F3 prod bug: `GET /api/providers` (no
trailing slash) used to 307-redirect, and behind a TLS-terminating proxy
the Location header downgraded to http://, which browsers block as mixed
content — the frontend then rendered Notion as disconnected. Both
spellings must be served directly, no redirect.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware import CurrentUser, get_current_user
from api.routes import providers
from api.workspace import get_active_team_id
from models.database import get_session

USER_ID = "00000000-0000-0000-0000-000000000001"
TEAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class _FakeScalars:
    def all(self) -> list[Any]:
        return []


class _FakeResult:
    def scalars(self) -> _FakeScalars:
        return _FakeScalars()


class _FakeSession:
    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(providers.router, prefix="/api/providers")

    async def _session() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID, github_username="octocat"
    )
    app.dependency_overrides[get_active_team_id] = lambda: TEAM_ID
    return app


def test_list_providers_no_trailing_slash_served_directly() -> None:
    client = TestClient(_make_app())
    resp = client.get("/api/providers", follow_redirects=False)
    assert resp.status_code == 200, "must not redirect (307 breaks behind TLS proxy)"
    ids = {p["id"] for p in resp.json()}
    assert {"github", "notion"} <= ids


def test_list_providers_trailing_slash_still_works() -> None:
    client = TestClient(_make_app())
    resp = client.get("/api/providers/", follow_redirects=False)
    assert resp.status_code == 200
    notion = next(p for p in resp.json() if p["id"] == "notion")
    assert notion["connected"] is False
