"""Knowledge store search endpoint.

Contract for B14 (MCP plugin). Response shape is locked — do not change.
Now wired to the real retriever (A9).
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from knowledge.retriever import retrieve
from models.database import get_session

router = APIRouter()


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="Natural-language query."),
    top_k: int = Query(10, ge=1, le=50),
    source: str | None = Query(None, pattern="^(github|notion)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    """Search indexed knowledge by semantic similarity."""
    chunks = await retrieve(
        query=q,
        user_id=user.id,
        session=session,
        top_k=top_k,
        source_filter=source,
    )
    return {
        "chunks": [
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
    }
