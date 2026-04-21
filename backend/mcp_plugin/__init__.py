"""B14 — Engram MCP plugin.

Exposes Engram's knowledge store to MCP clients (Cursor, Claude Code,
Claude Desktop) over stdio. Reaches the backend via HTTP using a JWT
issued by `/auth/login`.

Package renamed from `mcp` → `mcp_plugin` to avoid shadowing the official
`mcp` SDK on PyPI.

See `docs/v1/planning/partner-b-v1-plan.md` §"New track — MCP plugin".
"""
