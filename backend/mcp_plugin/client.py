"""Thin HTTP client against the Engram backend.

Architecture decision (Q3 in B14 scoping): the MCP plugin does NOT
touch the DB directly — it calls authenticated HTTP endpoints on the
Engram backend. This keeps business logic centralized and means the
plugin install story is "paste your Engram JWT into the config",
not "set up a local Postgres with pgvector".
"""

from typing import Any

import httpx


class EngramClient:
    def __init__(self, base_url: str, token: str, *, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout

    async def search_knowledge(
        self, query: str, top_k: int = 10, source: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"q": query, "top_k": top_k}
        if source:
            params["source"] = source
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(
                f"{self._base_url}/api/knowledge/search",
                params=params,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json().get("chunks", [])

    async def fetch_document(self, document_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(
                f"{self._base_url}/api/documents/{document_id}",
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
