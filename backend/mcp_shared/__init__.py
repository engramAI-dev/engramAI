"""Shared MCP wiring used by both the stdio plugin (`mcp_plugin`) and the
remote Streamable-HTTP endpoint (`api.routes.mcp`).

Holds the tool registry, the `build_server` factory, the dispatcher
protocol, and the LLM-facing formatters. Anything in here must stay
transport-agnostic — no HTTP, no FastAPI, no DB.
"""
