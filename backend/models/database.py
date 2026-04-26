"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

# Async engine + session (FastAPI routes)
engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine + session (Celery workers — D24/D28)
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(_sync_url, echo=settings.app_env == "development")
SyncSession = sessionmaker(sync_engine)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
