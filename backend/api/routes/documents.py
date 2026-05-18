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

    # Documents with chunk counts. metadata_ included so the frontend can
    # group Notion docs by workspace (notion_workspace_id lives there per
    # ingestion/notion.py).
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
            Document.metadata_,
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
                # Surface notion_workspace_id from metadata so the frontend can
                # render multiple Notion workspaces as separate rows. None for
                # GitHub docs and for pre-multi-workspace Notion rows.
                "workspace_id": (
                    row.metadata_.get("notion_workspace_id")
                    if row.source == "notion" and isinstance(row.metadata_, dict)
                    else None
                ),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
    }


def _build_line_map(chunks: list[Chunk]) -> dict[int, str]:
    """Reconstruct {line_no: line_text} from per-chunk contents.

    Chunks may overlap or have gaps; later chunks win on conflict (rare,
    but deterministic by chunk_index since callers pre-order). Notion
    chunks lacking start_line are skipped — padding is meaningless there.
    """
    lines: dict[int, str] = {}
    for c in chunks:
        if c.start_line is None:
            continue
        for i, text in enumerate(c.content.splitlines()):
            lines[c.start_line + i] = text
    return lines


def _pad_chunk(
    chunk: Chunk, line_map: dict[int, str], context_lines: int
) -> dict[str, int | str | None]:
    """Compute padded slice for a single chunk. Skips missing lines silently."""
    if chunk.start_line is None or chunk.end_line is None:
        return {
            "padded_content": None,
            "padded_start_line": None,
            "padded_end_line": None,
        }
    padded_start = max(1, chunk.start_line - context_lines)
    padded_end = chunk.end_line + context_lines
    rendered = "\n".join(
        line_map[n] for n in range(padded_start, padded_end + 1) if n in line_map
    )
    return {
        "padded_content": rendered,
        "padded_start_line": padded_start,
        "padded_end_line": padded_end,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    context_lines: int = Query(
        0,
        ge=0,
        le=50,
        description=(
            "Lines of surrounding context to include alongside each chunk. "
            "Adds padded_content / padded_start_line / padded_end_line "
            "fields when >0. Capped at 50."
        ),
    ),
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
    chunks = list(chunks_result.scalars().all())
    line_map = _build_line_map(chunks) if context_lines else {}

    chunk_payload: list[dict] = []
    for c in chunks:
        entry: dict = {
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
        "repo": doc.repo,
        "file_path": doc.file_path,
        "url": doc.url,
        "language": doc.language,
        "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
        "chunks": chunk_payload,
    }
