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
    team_id: str,
    session: AsyncSession,
    top_k: int = 10,
    source_filter: str | None = None,
) -> list[SourceChunk]:
    """Retrieve top-k chunks by cosine similarity (D30, D31).

    Returns SourceChunk objects compatible with ChatEngineResult.sources
    and the /knowledge/search contract.
    """
    logger.info(
        "retrieval_started",
        extra={
            "query_len": len(query),
            "user_id": user_id,
            "top_k": top_k,
            "source_filter": source_filter,
        },
    )

    try:
        # 1. Embed the query
        query_embedding = await _embed_query(query)
        vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # 2. Build pgvector similarity search query
        where_clause = "d.team_id = :team_id"
        params: dict = {"team_id": team_id, "top_k": top_k}

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
                c.metadata AS chunk_metadata,
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
    except Exception:
        logger.exception(
            "retrieval_failed",
            extra={"user_id": user_id, "query_len": len(query)},
        )
        raise

    # 3. Map to SourceChunk objects.
    # Line ranges are surfaced via the existing url + content_preview fields
    # (SourceChunk shape is a locked B contract, so we don't add new fields).
    chunks: list[SourceChunk] = []
    for row in rows:
        raw_preview = row.content[:200] if row.content else ""
        start, end = row.start_line, row.end_line
        line_label = ""
        if start is not None and end is not None and end >= start:
            line_label = f"L{start}" if start == end else f"L{start}-L{end}"

        # Line numbers only make sense for code (GitHub source). Notion's
        # start/end_line are post-conversion artifacts of our markdown-ish
        # rendering — they don't map to anything the user can see in Notion.
        is_code_source = row.source == "github"
        content_preview = (
            f"Lines {start}-{end} · {raw_preview}"
            if line_label and is_code_source and start != end
            else f"Line {start} · {raw_preview}"
            if line_label and is_code_source
            else raw_preview
        )

        url = row.url or ""
        if line_label and is_code_source and url:
            # GitHub blob URL anchor — jumps to the cited line range.
            anchor = (
                f"#L{start}-L{end}" if start != end else f"#L{start}"
            )
            url = f"{url}{anchor}"
        elif row.source == "notion" and url:
            # Notion block-level anchor — `#<block-id-without-dashes>` is the
            # format the Notion web UI uses to scroll to a specific block.
            chunk_meta = row.chunk_metadata or {}
            block_id = chunk_meta.get("notion_block_id") if isinstance(chunk_meta, dict) else None
            if block_id:
                url = f"{url}#{block_id.replace('-', '')}"

        chunks.append(SourceChunk(
            chunk_id=str(row.chunk_id),
            document_id=str(row.document_id),
            document_title=row.document_title or "",
            file_path=row.file_path,
            source=row.source,
            url=url,
            relevance_score=round(float(row.relevance_score), 4),
            content_preview=content_preview,
        ))

    top_score = chunks[0].relevance_score if chunks else None
    logger.info(
        "retrieval_completed",
        extra={
            "user_id": user_id,
            "chunk_count": len(chunks),
            "top_score": top_score,
            "source_filter": source_filter,
        },
    )
    return chunks
