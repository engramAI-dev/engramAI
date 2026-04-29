from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import auth, chat, documents, ingest, knowledge, outputs, providers
from api.usage_middleware import usage_tracking_middleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from models.database import engine

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

app.middleware("http")(usage_tracking_middleware)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(outputs.router, prefix="/api/outputs", tags=["outputs"])
app.include_router(providers.router, prefix="/api/providers", tags=["providers"])


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}