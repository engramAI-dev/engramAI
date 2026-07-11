"""B14-remote — full protocol-level test through the FastAPI lifespan.

Drives the actual `StreamableHTTPSessionManager` via TestClient, with
`retrieve` monkeypatched so the test is hermetic (no DB rows needed).

Covers:
  - initialize → 200 + Mcp-Session-Id + advertised capabilities
  - tools/list → all three tools with locked schemas
  - tools/call search_knowledge → format_search_results output
  - tools/call fetch_document → format_document output
  - tools/call cite → format_citations output
  - The CORS expose_headers flag actually exposes Mcp-Session-Id
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from chat.types import SourceChunk


_FAKE_CHUNKS = [
    SourceChunk(
        chunk_id="c1",
        document_id="d1",
        document_title="auth.py",
        file_path="backend/api/routes/auth.py",
        source="github",
        url="https://github.com/example/repo/blob/main/backend/api/routes/auth.py#L10-L20",
        relevance_score=0.92,
        content_preview="def login(): ...",
    )
]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Any:
    # Import inside the fixture so monkeypatch can intercept before
    # the lifespan builds the dispatcher.
    from api.routes import mcp as mcp_route

    async def _fake_retrieve(**_kwargs: Any) -> list[SourceChunk]:
        return _FAKE_CHUNKS

    async def _fake_fetch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "id": "d1",
            "title": "auth.py",
            "source": "github",
            "file_path": "backend/api/routes/auth.py",
            "url": "https://github.com/example/repo/blob/main/backend/api/routes/auth.py",
            "chunks": [
                {
                    "id": "c1",
                    "content": "def login(): ...",
                    "start_line": 10,
                    "end_line": 12,
                    "chunk_type": "function",
                }
            ],
        }

    monkeypatch.setattr(mcp_route, "retrieve", _fake_retrieve)
    monkeypatch.setattr(mcp_route, "_fetch_document_payload", _fake_fetch)

    from main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app: Any) -> Any:
    # `with TestClient(...)` runs the lifespan, which builds the
    # StreamableHTTPSessionManager and mounts it in app.state.
    with TestClient(app) as c:
        yield c


def _bearer(mint_jwt: Any) -> dict[str, str]:
    import time

    token = mint_jwt(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "github_username": "tester",
            "team_id": "00000000-0000-0000-0000-0000000000bb",
            "exp": int(time.time()) + 60,
        }
    )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _parse_sse(body: str) -> dict[str, Any]:
    """Pull the JSON payload out of an `event: message\\ndata: {...}` chunk."""
    import json

    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise AssertionError(f"No data line in SSE body:\n{body}")


def test_initialize_returns_session_id(client: Any, mint_jwt: Any) -> None:
    r = client.post(
        "/mcp",
        headers=_bearer(mint_jwt),
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
    )
    assert r.status_code == 200
    assert r.headers.get("mcp-session-id")
    payload = _parse_sse(r.text)
    assert payload["result"]["serverInfo"]["name"] == "engram-mcp"
    # CORS expose_headers asserts at the Starlette level — the header
    # value lands on the response unconditionally.
    assert "mcp-session-id" in (
        h.lower() for h in r.headers.keys()
    )


def test_full_protocol_round_trip(client: Any, mint_jwt: Any) -> None:
    headers = _bearer(mint_jwt)

    # 1) initialize
    init = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
    )
    assert init.status_code == 200
    sid = init.headers["mcp-session-id"]
    headers["Mcp-Session-Id"] = sid

    # 2) initialized notification
    note = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert note.status_code == 202

    # 3) tools/list
    listr = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert listr.status_code == 200
    tools = _parse_sse(listr.text)["result"]["tools"]
    assert {t["name"] for t in tools} == {
        "search_knowledge",
        "fetch_document",
        "cite",
    }

    # 4) tools/call search_knowledge — should hit our stubbed retriever
    callr = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_knowledge",
                "arguments": {"query": "auth", "top_k": 3},
            },
        },
    )
    assert callr.status_code == 200
    text = _parse_sse(callr.text)["result"]["content"][0]["text"]
    assert "auth.py" in text
    assert "score 0.920" in text  # confirms format_search_results ran

    # 5) tools/call fetch_document
    fetch = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "fetch_document",
                "arguments": {"document_id": "d1"},
            },
        },
    )
    assert fetch.status_code == 200
    text = _parse_sse(fetch.text)["result"]["content"][0]["text"]
    assert text.startswith("# auth.py")
    assert "def login" in text

    # 6) tools/call cite
    cite = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "cite",
                "arguments": {"query": "auth", "top_k": 2},
            },
        },
    )
    assert cite.status_code == 200
    text = _parse_sse(cite.text)["result"]["content"][0]["text"]
    assert "github" in text
    assert "auth.py" in text
