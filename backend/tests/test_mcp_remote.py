"""B14-remote — Streamable-HTTP `/mcp` transport tests.

Phase-2 surface only:
  - Auth gate: requests without a JWT are rejected before reaching the
    session manager.
  - LocalDispatcher: pulls user_id from the ContextVar, surfaces a
    clear error when called without one, calls retrieve() with the
    expected args.

Full end-to-end protocol-level tests (initialize → tools/list →
tools/call over HTTP) land in Phase 6 alongside the OAuth flow.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import mcp as mcp_route


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(mcp_route.router, prefix="/mcp")
    return TestClient(app)


def test_mcp_post_requires_auth(client: TestClient) -> None:
    r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert r.status_code == 401


def test_mcp_get_requires_auth(client: TestClient) -> None:
    r = client.get("/mcp")
    assert r.status_code == 401


def test_local_dispatcher_without_user_raises() -> None:
    dispatcher = mcp_route.LocalDispatcher()
    import asyncio

    async def _go() -> None:
        with pytest.raises(RuntimeError, match="without an authenticated user"):
            await dispatcher.search_knowledge("anything")

    asyncio.run(_go())


def test_local_dispatcher_passes_args_to_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def _fake_retrieve(**kwargs: Any) -> list[Any]:
        captured.update(kwargs)
        return []

    class _FakeSession:
        async def __aenter__(self) -> "_FakeSession":
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

    def _fake_session_factory() -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr(mcp_route, "retrieve", _fake_retrieve)
    monkeypatch.setattr(mcp_route, "async_session", _fake_session_factory)

    import asyncio

    async def _go() -> None:
        token = mcp_route._current_user_id.set("user-42")
        team_token = mcp_route._current_team_id.set(
            "00000000-0000-0000-0000-0000000000bb"
        )
        try:
            result = await mcp_route.LocalDispatcher().search_knowledge(
                "find auth code", top_k=7, source="github"
            )
        finally:
            mcp_route._current_team_id.reset(team_token)
            mcp_route._current_user_id.reset(token)
        assert result == []

    asyncio.run(_go())

    assert captured["user_id"] == "user-42"
    assert captured["query"] == "find auth code"
    assert captured["top_k"] == 7
    assert captured["source_filter"] == "github"
