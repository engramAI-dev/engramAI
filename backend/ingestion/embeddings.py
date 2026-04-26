"""A7 — Embedding pipeline.

Design: D23 (sequential batches of 128 + exponential backoff),
D24 (sync Celery task), D26 (official Voyage SDK).
"""

import logging
import time
import uuid

import voyageai
from sqlalchemy import select

from celery_app import celery
from config import settings
from models.chunk import Chunk
from models.database import SyncSession
from models.document import Document
from models.embedding import Embedding
from models.ingest_job import IngestJob

logger = logging.getLogger(__name__)

_BATCH_SIZE = 128
_MAX_RETRIES = 5
_BASE_DELAY = 2.0  # seconds


def _update_job(session, job_id: uuid.UUID, **kwargs) -> None:  # type: ignore[no-untyped-def]
    stmt = select(IngestJob).where(IngestJob.id == job_id)
    job = session.execute(stmt).scalar_one()
    for key, value in kwargs.items():
        setattr(job, key, value)
    session.commit()


def _get_chunks_for_job(session, job_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:  # type: ignore[no-untyped-def]
    """Get all chunks for a job's documents that don't have embeddings yet."""
    # Find the job to get user_id and identify documents created during this job
    job = session.execute(
        select(IngestJob).where(IngestJob.id == job_id)
    ).scalar_one()

    # Get all chunks for this user's documents that were created during this job
    # (documents without embeddings on their chunks)
    stmt = (
        select(Chunk.id, Chunk.content)
        .join(Document, Chunk.document_id == Document.id)
        .outerjoin(Embedding, Embedding.chunk_id == Chunk.id)
        .where(
            Document.user_id == job.user_id,
            Embedding.id.is_(None),  # no embedding yet
        )
    )
    results = session.execute(stmt).all()
    return [(row[0], row[1]) for row in results]


def _embed_batch_with_retry(
    client: voyageai.Client,
    texts: list[str],
) -> list[list[float]]:
    """Call Voyage embed with exponential backoff on rate limit."""
    for attempt in range(_MAX_RETRIES):
        try:
            result = client.embed(
                texts,
                model=settings.embedding_model,
                input_type="document",
            )
            return result.embeddings
        except Exception as exc:
            error_str = str(exc).lower()
            if "rate" in error_str or "429" in error_str:
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Voyage rate limit hit, retrying in %.1fs (attempt %d/%d)",
                    delay, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                raise
    raise RuntimeError(f"Voyage API failed after {_MAX_RETRIES} retries")


@celery.task(name="ingestion.embed_chunks", bind=True, max_retries=2)
def embed_chunks(
    self,  # type: ignore[no-untyped-def]
    job_id: str,
) -> None:
    """Embed all un-embedded chunks for a job's documents."""
    jid = uuid.UUID(job_id)

    try:
        # Get chunks to embed
        with SyncSession() as session:
            chunks = _get_chunks_for_job(session, jid)

        total = len(chunks)
        if total == 0:
            with SyncSession() as session:
                _update_job(session, jid, status="complete", progress=1.0)
            return

        logger.info("Embedding %d chunks for job %s", total, job_id)

        client = voyageai.Client(api_key=settings.voyage_api_key)
        embedded_count = 0

        # Process in batches (D23: sequential, batch size 128)
        for batch_start in range(0, total, _BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _BATCH_SIZE]
            chunk_ids = [c[0] for c in batch]
            texts = [c[1] for c in batch]

            # Get embeddings
            vectors = _embed_batch_with_retry(client, texts)

            # Store embeddings
            with SyncSession() as session:
                for chunk_id, vector in zip(chunk_ids, vectors):
                    session.add(Embedding(
                        id=uuid.uuid4(),
                        chunk_id=chunk_id,
                        embedding=vector,
                        model=settings.embedding_model,
                    ))
                session.commit()

            embedded_count += len(batch)
            # Progress: 80% was chunking, embedding fills 80% → 100%
            progress = 0.8 + (embedded_count / total) * 0.2

            with SyncSession() as session:
                _update_job(session, jid, progress=progress)

            logger.info("Embedded %d/%d chunks for job %s", embedded_count, total, job_id)

        # Mark complete
        with SyncSession() as session:
            _update_job(session, jid, status="complete", progress=1.0)

        logger.info("Embedding complete for job %s", job_id)

    except Exception as exc:
        logger.exception("Embedding failed for job %s", job_id)
        with SyncSession() as session:
            _update_job(session, jid, status="failed", error_message=str(exc)[:1000])
        raise
