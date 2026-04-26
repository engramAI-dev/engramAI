"""A7 — Embedding pipeline.

Design: D23 (sequential batches of 128), D24 (sync Celery task),
D44 (local model via sentence-transformers).
"""

import logging
import uuid

from sentence_transformers import SentenceTransformer
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

# Module-level model — loaded once per worker process
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (one-time ~270MB download on first use)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model, trust_remote_code=True)
        logger.info("Embedding model loaded")
    return _model


def _update_job(session, job_id: uuid.UUID, **kwargs) -> None:  # type: ignore[no-untyped-def]
    stmt = select(IngestJob).where(IngestJob.id == job_id)
    job = session.execute(stmt).scalar_one()
    for key, value in kwargs.items():
        setattr(job, key, value)
    session.commit()


def _get_chunks_for_job(session, job_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:  # type: ignore[no-untyped-def]
    """Get all chunks for a job's documents that don't have embeddings yet."""
    job = session.execute(
        select(IngestJob).where(IngestJob.id == job_id)
    ).scalar_one()

    stmt = (
        select(Chunk.id, Chunk.content)
        .join(Document, Chunk.document_id == Document.id)
        .outerjoin(Embedding, Embedding.chunk_id == Chunk.id)
        .where(
            Document.user_id == job.user_id,
            Embedding.id.is_(None),
        )
    )
    results = session.execute(stmt).all()
    return [(row[0], row[1]) for row in results]


@celery.task(name="ingestion.embed_chunks", bind=True, max_retries=2)
def embed_chunks(
    self,  # type: ignore[no-untyped-def]
    job_id: str,
) -> None:
    """Embed all un-embedded chunks for a job's documents."""
    jid = uuid.UUID(job_id)

    try:
        with SyncSession() as session:
            chunks = _get_chunks_for_job(session, jid)

        total = len(chunks)
        if total == 0:
            with SyncSession() as session:
                _update_job(session, jid, status="complete", progress=1.0)
            return

        logger.info("Embedding %d chunks for job %s", total, job_id)

        model = _get_model()
        embedded_count = 0

        for batch_start in range(0, total, _BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _BATCH_SIZE]
            chunk_ids = [c[0] for c in batch]
            texts = [c[1] for c in batch]

            # Embed locally — no API call, no rate limits
            vectors = model.encode(texts, normalize_embeddings=True).tolist()

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
            progress = 0.8 + (embedded_count / total) * 0.2

            with SyncSession() as session:
                _update_job(session, jid, progress=progress)

            logger.info("Embedded %d/%d chunks for job %s", embedded_count, total, job_id)

        with SyncSession() as session:
            _update_job(session, jid, status="complete", progress=1.0)

        logger.info("Embedding complete for job %s", job_id)

    except Exception as exc:
        logger.exception("Embedding failed for job %s", job_id)
        with SyncSession() as session:
            _update_job(session, jid, status="failed", error_message=str(exc)[:1000])
        raise
