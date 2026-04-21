"""B14 — `/api/knowledge/search` contract tests.

Stub route (A9 wires the real retriever later). Just verifies the
shape and auth guard so the MCP plugin can build against it.
"""

import time
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import knowledge


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(knowledge.router, prefix="/api/knowledge")
    return TestClient(app)


def test_search_requires_auth(client: TestClient) -> None:
    r = client.get("/api/knowledge/search", params={"q": "hello"})
    assert r.status_code == 401


def test_search_stub_returns_empty_chunks(client: TestClient, mint_jwt: Any) -> None:
    token = mint_jwt({"sub": "u1", "github_username": "alice", "exp": int(time.time()) + 60})
    r = client.get(
        "/api/knowledge/search",
        params={"q": "hello", "top_k": 5, "source": "github"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"chunks": []}


def test_search_validates_top_k_upper_bound(client: TestClient, mint_jwt: Any) -> None:
    token = mint_jwt({"sub": "u1", "github_username": "alice", "exp": int(time.time()) + 60})
    r = client.get(
        "/api/knowledge/search",
        params={"q": "hello", "top_k": 999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_search_validates_source_enum(client: TestClient, mint_jwt: Any) -> None:
    token = mint_jwt({"sub": "u1", "github_username": "alice", "exp": int(time.time()) + 60})
    r = client.get(
        "/api/knowledge/search",
        params={"q": "hello", "source": "gitlab"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
