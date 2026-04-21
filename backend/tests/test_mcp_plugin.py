"""B14 — MCP plugin tests.

Hermetic: stub the EngramClient, drive tool dispatch directly. No real
HTTP, no MCP transport. When A9 lands, add integration tests that hit
the real `/api/knowledge/search` endpoint.
"""

from typing import Any

import pytest

from mcp_plugin.formatting import format_document, format_search_results
from mcp_plugin.server import TOOLS, _dispatch


class _StubClient:
    def __init__(
        self,
        *,
        chunks: list[dict[str, Any]] | None = None,
        doc: dict[str, Any] | None = None,
    ) -> None:
        self.chunks = chunks or []
        self.doc = doc or {}
        self.last_search: dict[str, Any] | None = None
        self.last_fetch: str | None = None

    async def search_knowledge(
        self, query: str, top_k: int = 10, source: str | None = None
    ) -> list[dict[str, Any]]:
        self.last_search = {"query": query, "top_k": top_k, "source": source}
        return self.chunks

    async def fetch_document(self, document_id: str) -> dict[str, Any]:
        self.last_fetch = document_id
        return self.doc


def test_tool_surface_matches_scope() -> None:
    names = {t.name for t in TOOLS}
    assert names == {"search_knowledge", "fetch_document"}


def test_search_tool_schema_requires_query() -> None:
    tool = next(t for t in TOOLS if t.name == "search_knowledge")
    schema = tool.inputSchema
    assert schema["required"] == ["query"]
    top_k = schema["properties"]["top_k"]
    assert top_k["minimum"] == 1
    assert top_k["maximum"] == 50
    assert schema["properties"]["source"]["enum"] == ["github", "notion"]


@pytest.mark.asyncio
async def test_dispatch_search_knowledge_passes_args_and_formats() -> None:
    client = _StubClient(
        chunks=[
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "document_title": "auth module",
                "file_path": "backend/auth.py",
                "source": "github",
                "url": "https://github.com/x/y/blob/main/backend/auth.py",
                "relevance_score": 0.91,
                "content_preview": "def login(...):",
            }
        ]
    )
    out = await _dispatch(
        client, "search_knowledge", {"query": "login flow", "top_k": 5, "source": "github"}
    )
    assert client.last_search == {"query": "login flow", "top_k": 5, "source": "github"}
    assert "auth module" in out
    assert "0.910" in out
    assert "backend/auth.py" in out


@pytest.mark.asyncio
async def test_dispatch_search_knowledge_handles_empty() -> None:
    out = await _dispatch(_StubClient(), "search_knowledge", {"query": "anything"})
    assert "No results" in out


@pytest.mark.asyncio
async def test_dispatch_fetch_document_formats_content() -> None:
    client = _StubClient(
        doc={
            "id": "d1",
            "title": "Architecture",
            "source": "notion",
            "file_path": None,
            "url": "https://notion.so/abc",
            "content": "# Overview\n...",
        }
    )
    out = await _dispatch(client, "fetch_document", {"document_id": "d1"})
    assert client.last_fetch == "d1"
    assert "Architecture" in out
    assert "notion" in out
    assert "notion.so/abc" in out


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises() -> None:
    with pytest.raises(ValueError):
        await _dispatch(_StubClient(), "bogus", {})


def test_format_search_includes_all_fields() -> None:
    text = format_search_results(
        [
            {
                "document_title": "T",
                "source": "github",
                "file_path": "a.py",
                "url": "https://x",
                "relevance_score": 0.5,
                "content_preview": "preview",
            }
        ]
    )
    assert "T" in text and "github" in text and "a.py" in text and "preview" in text


def test_format_document_handles_missing_url_and_path() -> None:
    text = format_document({"title": "X", "source": "github", "content": "body"})
    assert "X" in text and "body" in text
