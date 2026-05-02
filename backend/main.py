from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from logging_setup import setup_logging
from sentry_setup import init_sentry

# Initialize structured logging before importing any module that may instantiate
# loggers at import time. Late imports below are intentional — ruff E402 is muted.
setup_logging(level=settings.log_level)
init_sentry(settings.sentry_dsn, settings.app_env)

from api.routes import admin, auth, chat, documents, ingest, knowledge, mcp as mcp_route, outputs, providers  # noqa: E402
from api.request_id_middleware import request_id_middleware  # noqa: E402
from api.usage_middleware import usage_tracking_middleware  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from models.database import engine
    from mcp_shared.server import build_server

    mcp_server = build_server(mcp_route.LocalDispatcher())
    mcp_manager = StreamableHTTPSessionManager(app=mcp_server, stateless=False)
    async with mcp_manager.run():
        app.state.mcp_session_manager = mcp_manager
        yield
    await engine.dispose()


app = FastAPI(
    title="Engram",
    description="Engineering intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Order matters — last-registered middleware runs OUTERMOST. We want
# request_id outermost so it sets the contextvar before usage_tracking
# (and any inner middleware/route) emits a log line.
app.middleware("http")(usage_tracking_middleware)
app.middleware("http")(request_id_middleware)

app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(outputs.router, prefix="/api/outputs", tags=["outputs"])
app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
# MCP: no /api prefix — connector URLs (claude.ai, Cursor) expect /mcp directly.
app.include_router(mcp_route.router, prefix="/mcp", tags=["mcp"])


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}