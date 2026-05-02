"""MCP tool registry — one source of truth for both transports.

Adding a tool means: append a `Tool(...)` entry here AND a branch in
`mcp_shared.server._dispatch`. The dispatcher protocol is satisfied by
both `mcp_plugin.client.EngramClient` (HTTP) and the in-process
`api.routes.mcp` LocalDispatcher.
"""

from typing import Any, Protocol

from mcp.types import Tool

TOOLS: list[Tool] = [
    Tool(
        name="search_knowledge",
        description=(
            "Search Engram's indexed GitHub + Notion knowledge store. "
            "Returns ranked SourceChunk results with relevance scores, "
            "document titles, file paths, and content previews."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language query."},
                "top_k": {
                    "type": "integer",
                    "description": "Max results (default 10, max 50).",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
                "source": {
                    "type": "string",
                    "enum": ["github", "notion"],
                    "description": "Optional source filter.",
                },
                "intent": {
                    "type": "string",
                    "enum": ["explain", "generate", "question"],
                    "description": (
                        "Optional response shaping. 'generate' floats code "
                        "results above docs; 'question' floats docs above "
                        "code; 'explain' keeps default ranking. Format-only "
                        "— retrieval scores are not changed."
                    ),
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="fetch_document",
        description=(
            "Fetch a full indexed document (code file or Notion page) by id. "
            "Use this after `search_knowledge` surfaces a document of interest."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "context_lines": {
                    "type": "integer",
                    "description": (
                        "Lines of surrounding context to include alongside "
                        "each chunk. 0 returns chunks as-stored. Capped at 50."
                    ),
                    "minimum": 0,
                    "maximum": 50,
                    "default": 0,
                },
            },
            "required": ["document_id"],
        },
    ),
    Tool(
        name="cite",
        description=(
            "Return locators only (source, path, line range, URL) for an "
            "answer the LLM has already drafted. Cheaper on context than "
            "`search_knowledge` when previews aren't needed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic or claim to cite — the answer text.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max citations (default 5, max 20).",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
]


class Dispatcher(Protocol):
    """What both transports must provide to `build_server`."""

    async def search_knowledge(
        self, query: str, top_k: int = 10, source: str | None = None
    ) -> list[dict[str, Any]]: ...

    async def fetch_document(
        self, document_id: str, context_lines: int = 0
    ) -> dict[str, Any]: ...
