"""Document listing and detail endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from models.chunk import Chunk
from models.database import get_session
from models.document import Document

router = APIRouter()


@router.get("/")
async def list_documents(
    source: str | None = Query(None, pattern="^(github|notion)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List all indexed documents for the current user."""
    uid = uuid.UUID(user.id)
    where = [Document.user_id == uid]
    if source:
        where.append(Document.source == source)

    # Total count
    count_result = await session.execute(
        select(func.count(Document.id)).where(*where)
    )
    total = count_result.scalar_one()

    # Documents with chunk counts
    stmt = (
        select(
            Document.id,
            Document.title,
            Document.source,
            Document.repo,
            Document.file_path,
            Document.url,
            Document.language,
            Document.indexed_at,
            func.count(Chunk.id).label("chunk_count"),
        )
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(*where)
        .group_by(Document.id)
        .order_by(Document.indexed_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    return {
        "documents": [
            {
                "id": str(row.id),
                "title": row.title,
                "source": row.source,
                "repo": row.repo,
                "file_path": row.file_path,
                "url": row.url,
                "language": row.language,
                "indexed_at": row.indexed_at.isoformat() if row.indexed_at else None,
                "chunk_count": row.chunk_count,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get details for a specific document."""
    uid = uuid.UUID(user.id)
    result = await session.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id),
            Document.user_id == uid,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get chunks
    chunks_result = await session.execute(
        select(Chunk)
        .where(Chunk.document_id == doc.id)
        .order_by(Chunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()

    return {
        "id": str(doc.id),
        "title": doc.title,
        "source": doc.source,
        "repo": doc.repo,
        "file_path": doc.file_path,
        "url": doc.url,
        "language": doc.language,
        "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
        "chunks": [
            {
                "id": str(c.id),
                "content": c.content,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "chunk_type": c.chunk_type,
            }
            for c in chunks
        ],
    }
