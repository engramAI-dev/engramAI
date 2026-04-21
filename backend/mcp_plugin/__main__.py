"""Run the Engram MCP plugin over stdio.

    python -m mcp_plugin

Requires:
  - ENGRAM_BASE_URL (default: http://localhost:8000)
  - ENGRAM_TOKEN    (JWT from /auth/login)
"""

import asyncio
import os
import sys

from mcp.server.stdio import stdio_server

from mcp_plugin.client import EngramClient
from mcp_plugin.server import build_server


async def main() -> None:
    base_url = os.environ.get("ENGRAM_BASE_URL", "http://localhost:8000")
    token = os.environ.get("ENGRAM_TOKEN")
    if not token:
        print("ENGRAM_TOKEN is required", file=sys.stderr)
        sys.exit(2)

    client = EngramClient(base_url=base_url, token=token)
    server = build_server(client)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
