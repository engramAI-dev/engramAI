"""MCP server entrypoint.

Two tools in the v1/v1.5 first cut (Q4/Q8 decision):
  - search_knowledge(query, top_k?, source?)
  - fetch_document(document_id)

`list_sources` is a v1 stretch if velocity allows post-gate; add
by appending to TOOLS and a new branch in `_dispatch`.
"""

from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_plugin.client import EngramClient
from mcp_plugin.formatting import (
    format_citations,
    format_document,
    format_search_results,
)

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


def build_server(client: EngramClient) -> Server:
    server: Server = Server("engram-mcp")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        text = await _dispatch(client, name, arguments)
        return [TextContent(type="text", text=text)]

    return server


async def _dispatch(client: EngramClient, name: str, arguments: dict[str, Any]) -> str:
    if name == "search_knowledge":
        chunks = await client.search_knowledge(
            query=arguments["query"],
            top_k=arguments.get("top_k", 10),
            source=arguments.get("source"),
        )
        return format_search_results(chunks, intent=arguments.get("intent"))
    if name == "cite":
        chunks = await client.search_knowledge(
            query=arguments["query"],
            top_k=arguments.get("top_k", 5),
        )
        return format_citations(chunks)
    if name == "fetch_document":
        doc = await client.fetch_document(
            arguments["document_id"],
            context_lines=arguments.get("context_lines", 0),
        )
        return format_document(doc)
    raise ValueError(f"Unknown tool: {name}")
