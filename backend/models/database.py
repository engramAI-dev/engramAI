"""Database connection and session management."""

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


def _async_connect_args(url: str) -> dict[str, Any]:
    """Connect args for create_async_engine.

    Neon's pooler endpoint (`-pooler` in hostname) runs pgbouncer in
    transaction mode, which doesn't support asyncpg's prepared-statement
    cache. Disable the cache when we detect a pooler URL — failing to
    do so produces "prepared statement '...' already exists" runtime
    errors a few hours into a deploy.
    """
    if "-pooler" in url:
        return {"statement_cache_size": 0}
    return {}


# Async engine + session (FastAPI routes)
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    connect_args=_async_connect_args(settings.database_url),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def _to_sync_url(url: str) -> str:
    """Convert the runtime asyncpg URL into a psycopg2-compatible one.

    asyncpg accepts `ssl=require`; psycopg2 (libpq) only understands
    `sslmode=require` and raises `invalid connection option "ssl"`
    otherwise. We swap both the driver prefix and the SSL query param
    so a single `DATABASE_URL` can drive both engines.
    """
    return (
        url.replace("+asyncpg", "+psycopg2")
        .replace("?ssl=", "?sslmode=")
        .replace("&ssl=", "&sslmode=")
    )


# Sync engine + session (Celery workers — D24/D28)
_sync_url = _to_sync_url(settings.database_url)
sync_engine = create_engine(_sync_url, echo=settings.app_env == "development")
SyncSession = sessionmaker(sync_engine)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
