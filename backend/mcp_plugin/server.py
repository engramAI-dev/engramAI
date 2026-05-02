"""Stdio-plugin server wiring.

Thin shim — the actual `Server`, `TOOLS`, and `_dispatch` now live in
`mcp_shared` so the remote Streamable-HTTP transport can reuse them.
"""

from mcp_plugin.client import EngramClient
from mcp_shared.server import build_server as _build_server


def build_server(client: EngramClient):
    """Build an MCP server backed by the HTTP-talking `EngramClient`.

    `EngramClient` already satisfies the `mcp_shared.tools.Dispatcher`
    protocol (async `search_knowledge`, `fetch_document`).
    """
    return _build_server(client)
