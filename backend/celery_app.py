"""A4 — Celery application setup.

Importable standalone — does NOT import the FastAPI app (no circular deps).
Uses Redis broker from settings.
"""

from celery import Celery

from config import settings

celery = Celery(
    "engram",
    broker=settings.redis_url,
    # D7: No result backend — we track job state in our own ingest_jobs table.
    result_backend=None,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Autodiscover tasks in the ingestion package.
celery.autodiscover_tasks(["ingestion"])
