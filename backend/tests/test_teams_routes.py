"""Team / workspace route tests — hermetic, no DB.

Covers `GET /teams` (dashboard list), `POST /teams` (creation — disabled by
entitlement in the OSS build), and `PATCH /teams/{id}` (owner-only rename).
A `_FakeSession` returns queued results per `execute()` call in route order.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import teams
from models.database import get_session
from models.membership import Membership
from models.team import Team

USER_ID = "00000000-0000-0000-0000-000000000001"


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def first(self) -> Any:
        return self._value

    def all(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeSession:
    """Pops a queued value per execute() call, in route-issue order."""

    def __init__(self, results: list[Any]) -> None:
        self.results = list(results)
        self.committed = False
        self.added: list[Any] = []

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self.results.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


def _make_app(session: _FakeSession) -> FastAPI:
    app = FastAPI()
    app.include_router(teams.router, prefix="/api/teams")

    async def _override() -> AsyncIterator[_FakeSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    return app


@pytest.fixture
def auth_headers(mint_jwt: Any) -> dict[str, str]:
    token = mint_jwt(
        {"sub": USER_ID, "github_username": "alice", "exp": int(time.time()) + 60}
    )
    return {"Authorization": f"Bearer {token}"}


def _team(name: str = "Backend", plan: str = "free") -> Team:
    return Team(id=uuid.uuid4(), name=name, slug="backend", is_default=True, plan=plan)


def _membership(role: str = "owner") -> Membership:
    return Membership(
        id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        user_id=uuid.UUID(USER_ID),
        role=role,
        onboarding_state="ready",
    )


def test_all_routes_require_auth() -> None:
    client = TestClient(_make_app(_FakeSession([])))
    assert client.get("/api/teams").status_code == 401
    assert client.post("/api/teams", json={"name": "X"}).status_code == 401
    assert client.patch(f"/api/teams/{uuid.uuid4()}", json={"name": "X"}).status_code == 401


def test_list_returns_workspaces_with_onboarding_state(auth_headers: dict[str, str]) -> None:
    session = _FakeSession([[(_team(), _membership())]])
    client = TestClient(_make_app(session))
    r = client.get("/api/teams", headers=auth_headers)
    assert r.status_code == 200
    card = r.json()["workspaces"][0]
    assert card["name"] == "Backend"
    assert card["onboarding_state"] == "ready"


def test_list_empty(auth_headers: dict[str, str]) -> None:
    client = TestClient(_make_app(_FakeSession([[]])))
    r = client.get("/api/teams", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"workspaces": []}


def test_create_disabled_in_oss_returns_402(auth_headers: dict[str, str]) -> None:
    # resolve_current_team → (default team, owner); can_create_teams is False in
    # the OSS single tier, so creation is disabled by entitlement.
    session = _FakeSession([(_team(), "owner")])
    client = TestClient(_make_app(session))
    r = client.post("/api/teams", json={"name": "Second"}, headers=auth_headers)
    assert r.status_code == 402
    assert "available" in r.json()["detail"].lower()


def test_rename_owner_succeeds(auth_headers: dict[str, str]) -> None:
    team = _team(name="Old")
    session = _FakeSession([(team, "owner")])
    client = TestClient(_make_app(session))
    r = client.patch(f"/api/teams/{uuid.uuid4()}", json={"name": "New"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "New"
    assert team.name == "New"


def test_rename_non_owner_forbidden(auth_headers: dict[str, str]) -> None:
    session = _FakeSession([(_team(), "member")])
    client = TestClient(_make_app(session))
    r = client.patch(f"/api/teams/{uuid.uuid4()}", json={"name": "New"}, headers=auth_headers)
    assert r.status_code == 403


def test_rename_missing_404(auth_headers: dict[str, str]) -> None:
    session = _FakeSession([None])
    client = TestClient(_make_app(session))
    r = client.patch(f"/api/teams/{uuid.uuid4()}", json={"name": "New"}, headers=auth_headers)
    assert r.status_code == 404


def test_rename_bad_uuid_404(auth_headers: dict[str, str]) -> None:
    client = TestClient(_make_app(_FakeSession([])))
    r = client.patch("/api/teams/not-a-uuid", json={"name": "New"}, headers=auth_headers)
    assert r.status_code == 404
