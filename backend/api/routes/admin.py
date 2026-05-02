"""Admin routes: user-scoped library wipe + dev-only provider disconnect.

`POST /api/admin/wipe-library` — user-visible "danger zone" action. Deletes
the caller's `documents` (cascading to `chunks` and `embeddings`) and
`ingest_jobs`. Connections, conversations, messages, and outputs are
preserved.

`POST /api/admin/disconnect/{provider}` — gated on `ENGRAM_DEBUG_ENDPOINTS`.
Drops the caller's `user_connections` row so the provider OAuth flow can be
re-exercised end-to-end during testing. Not exposed to end users; UI button
only renders when `NEXT_PUBLIC_DEBUG=1`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from config import settings
from models.database import get_session
from models.document import Document
from models.ingest_job import IngestJob
from models.user_connection import UserConnection

router = APIRouter()


class WipeLibraryResponse(BaseModel):
    documents_deleted: int
    ingest_jobs_deleted: int


class DisconnectResponse(BaseModel):
    provider: str
    deleted: bool


@router.post("/wipe-library", response_model=WipeLibraryResponse)
async def wipe_library(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WipeLibraryResponse:
    user_uuid = uuid.UUID(user.id)

    docs_result = await session.execute(
        delete(Document).where(Document.user_id == user_uuid)
    )
    jobs_result = await session.execute(
        delete(IngestJob).where(IngestJob.user_id == user_uuid)
    )
    await session.commit()

    return WipeLibraryResponse(
        documents_deleted=docs_result.rowcount or 0,
        ingest_jobs_deleted=jobs_result.rowcount or 0,
    )


@router.post("/disconnect/{provider}", response_model=DisconnectResponse)
async def disconnect_provider(
    provider: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DisconnectResponse:
    if not settings.engram_debug_endpoints:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )

    result = await session.execute(
        delete(UserConnection).where(
            UserConnection.user_id == uuid.UUID(user.id),
            UserConnection.provider == provider,
        )
    )
    await session.commit()

    return DisconnectResponse(provider=provider, deleted=(result.rowcount or 0) > 0)
