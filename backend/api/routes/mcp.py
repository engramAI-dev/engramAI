"""Remote MCP transport — Streamable HTTP at `/mcp`.

Architecture:
  - One MCP `Server` + `StreamableHTTPSessionManager` built at app
    startup (see `lifespan` wiring in `main.py`).
  - Per-request auth: the JWT is decoded by `get_current_user`, the
    user id is pushed into a ContextVar, then the ASGI request is handed
    to the session manager.
  - `LocalDispatcher` (in-process) reads the user from the ContextVar
    and acquires a fresh DB session per tool call. No self-HTTP, no
    contextvar leak across requests.

Why a ContextVar and not a manager-side hook: the MCP SDK builds tool
handlers once and has no native concept of per-request auth context.
ContextVars are async-safe in Starlette/anyio and survive across the
session manager's task spawning.
"""

from contextvars import ContextVar
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from knowledge.retriever import retrieve
from models.chunk import Chunk
from models.database import async_session
from models.document import Document

router = APIRouter()

# Rate limiting note: not enforced programmatically in v1.5. The auth
# token IS the rate limit — abuse → revoke from /settings. Move to a
# Redis-backed slowapi limiter when we add multi-instance deploy or
# anonymous OAuth-issued tokens (Phase 4 follow-up).

# Per-request user context. Set by the route handler before delegating
# to the MCP session manager; read by LocalDispatcher in tool calls.
_current_user_id: ContextVar[str | None] = ContextVar("mcp_current_user_id", default=None)


class LocalDispatcher:
    """In-process implementation of `mcp_shared.tools.Dispatcher`.

    Calls the retriever and the documents service directly — no HTTP
    self-loop. User identity comes from the ContextVar set by the route.
    Each tool invocation acquires its own short-lived DB session.
    """

    async def search_knowledge(
        self, query: str, top_k: int = 10, source: str | None = None
    ) -> list[dict[str, Any]]:
        user_id = _require_user_id()
        async with async_session() as session:
            chunks = await retrieve(
                query=query,
                user_id=user_id,
                session=session,
                top_k=top_k,
                source_filter=source,
            )
        return [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "document_title": c.document_title,
                "file_path": c.file_path,
                "source": c.source,
                "url": c.url,
                "relevance_score": c.relevance_score,
                "content_preview": c.content_preview,
            }
            for c in chunks
        ]

    async def fetch_document(
        self, document_id: str, context_lines: int = 0
    ) -> dict[str, Any]:
        user_id = _require_user_id()
        async with async_session() as session:
            return await _fetch_document_payload(
                document_id, user_id, session, context_lines
            )


def _require_user_id() -> str:
    user_id = _current_user_id.get()
    if not user_id:
        raise RuntimeError("MCP tool call without an authenticated user")
    return user_id


async def _fetch_document_payload(
    document_id: str,
    user_id: str,
    session: AsyncSession,
    context_lines: int,
) -> dict[str, Any]:
    """Mirror of `api.routes.documents.get_document` payload shape so
    `mcp_shared.formatting.format_document` keeps working unchanged.

    Inlined deliberately: the route handler is FastAPI-bound (Depends,
    HTTPException) and not callable from a non-HTTP dispatcher. If a
    third caller appears, lift this into `knowledge/service.py`.
    """
    from api.routes.documents import _build_line_map, _pad_chunk

    uid = uuid.UUID(user_id)
    result = await session.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id),
            Document.user_id == uid,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return {"title": "(not found)", "source": "?", "content": ""}

    chunks_result = await session.execute(
        select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
    )
    chunks = list(chunks_result.scalars().all())
    line_map = _build_line_map(chunks) if context_lines else {}

    chunk_payload: list[dict[str, Any]] = []
    for c in chunks:
        entry: dict[str, Any] = {
            "id": str(c.id),
            "content": c.content,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "chunk_type": c.chunk_type,
        }
        if context_lines:
            entry.update(_pad_chunk(c, line_map, context_lines))
        chunk_payload.append(entry)

    return {
        "id": str(doc.id),
        "title": doc.title,
        "source": doc.source,
        "file_path": doc.file_path,
        "url": doc.url,
        "chunks": chunk_payload,
    }


async def _handle_mcp_request(request: Request, user: CurrentUser) -> Response:
    manager = getattr(request.app.state, "mcp_session_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP transport not initialized",
        )

    # Tag Sentry events from MCP traffic so dashboards can split MCP
    # errors from the web app without parsing URLs. No-op when Sentry
    # is not initialized (the SDK swallows tag calls outside a scope).
    try:
        import sentry_sdk

        sentry_sdk.set_tag("transport", "mcp")
        sentry_sdk.set_user({"id": user.id, "username": user.github_username})
    except Exception:
        pass

    token = _current_user_id.set(user.id)
    try:
        await manager.handle_request(request.scope, request.receive, request._send)
    finally:
        _current_user_id.reset(token)
    # `handle_request` writes the response itself; FastAPI just needs us
    # to return *something* it won't double-send. An empty Response with
    # the body already flushed is the canonical pattern.
    return Response(status_code=200)


@router.post("")
@router.post("/")
async def mcp_post(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """JSON-RPC requests (initialize, tools/list, tools/call)."""
    return await _handle_mcp_request(request, user)


@router.get("")
@router.get("/")
async def mcp_get(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Server→client SSE stream for protocol notifications."""
    return await _handle_mcp_request(request, user)


@router.delete("")
@router.delete("/")
async def mcp_delete(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Session termination."""
    return await _handle_mcp_request(request, user)
