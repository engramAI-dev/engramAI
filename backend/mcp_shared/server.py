"""Transport-agnostic MCP server factory.

`build_server(dispatcher)` returns an `mcp.server.Server` whose
`call_tool` handler runs the dispatcher and renders the result via
`mcp_shared.formatting`. The same factory is used by:

  - `mcp_plugin.__main__` over stdio with an HTTP-backed dispatcher
  - `api.routes.mcp` over Streamable HTTP with an in-process dispatcher
"""

from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_shared.formatting import (
    format_citations,
    format_document,
    format_search_results,
)
from mcp_shared.tools import TOOLS, Dispatcher


def build_server(dispatcher: Dispatcher) -> Server:
    server: Server = Server("engram-mcp")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        text = await _dispatch(dispatcher, name, arguments)
        return [TextContent(type="text", text=text)]

    return server


async def _dispatch(
    dispatcher: Dispatcher, name: str, arguments: dict[str, Any]
) -> str:
    if name == "search_knowledge":
        chunks = await dispatcher.search_knowledge(
            query=arguments["query"],
            top_k=arguments.get("top_k", 10),
            source=arguments.get("source"),
        )
        return format_search_results(chunks, intent=arguments.get("intent"))
    if name == "cite":
        chunks = await dispatcher.search_knowledge(
            query=arguments["query"],
            top_k=arguments.get("top_k", 5),
        )
        return format_citations(chunks)
    if name == "fetch_document":
        doc = await dispatcher.fetch_document(
            arguments["document_id"],
            context_lines=arguments.get("context_lines", 0),
        )
        return format_document(doc)
    raise ValueError(f"Unknown tool: {name}")
