"""A9 — Vector retrieval layer.

Design: D29 (inline async query embedding via run_in_executor),
D30 (cosine), D31 (pgvector only), D44 (local sentence-transformers model).
"""

import asyncio
import logging

from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from chat.types import SourceChunk
from config import settings

logger = logging.getLogger(__name__)

# Module-level model — loaded once per process
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model, trust_remote_code=True)
    return _model


async def _embed_query(query: str) -> list[float]:
    """Embed a query string locally, async via run_in_executor (D29)."""
    loop = asyncio.get_event_loop()

    def _sync_embed() -> list[float]:
        model = _get_model()
        vector = model.encode(query, normalize_embeddings=True)
        return vector.tolist()

    return await loop.run_in_executor(None, _sync_embed)


async def retrieve(
    query: str,
    user_id: str,
    session: AsyncSession,
    top_k: int = 10,
    source_filter: str | None = None,
) -> list[SourceChunk]:
    """Retrieve top-k chunks by cosine similarity (D30, D31).

    Returns SourceChunk objects compatible with ChatEngineResult.sources
    and the /knowledge/search contract.
    """
    # 1. Embed the query
    query_embedding = await _embed_query(query)
    vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # 2. Build pgvector similarity search query
    where_clause = "d.user_id = :user_id"
    params: dict = {"user_id": user_id, "top_k": top_k}

    if source_filter:
        where_clause += " AND d.source = :source_filter"
        params["source_filter"] = source_filter

    sql = text(f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            c.start_line,
            c.end_line,
            d.title AS document_title,
            d.file_path,
            d.source,
            d.url,
            1 - (e.embedding <=> '{vec_literal}'::vector) AS relevance_score
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE {where_clause}
        ORDER BY e.embedding <=> '{vec_literal}'::vector
        LIMIT :top_k
    """)

    result = await session.execute(sql, params)
    rows = result.fetchall()

    # 3. Map to SourceChunk objects
    chunks: list[SourceChunk] = []
    for row in rows:
        content_preview = row.content[:200] if row.content else ""
        chunks.append(SourceChunk(
            chunk_id=str(row.chunk_id),
            document_id=str(row.document_id),
            document_title=row.document_title or "",
            file_path=row.file_path,
            source=row.source,
            url=row.url or "",
            relevance_score=round(float(row.relevance_score), 4),
            content_preview=content_preview,
        ))

    return chunks
