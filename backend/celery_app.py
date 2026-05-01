"""A4 — Celery application setup.

Importable standalone — does NOT import the FastAPI app (no circular deps).
Uses Redis broker from settings.
"""

from celery import Celery

from config import settings
from logging_setup import setup_logging
from sentry_setup import init_sentry

# Worker process needs the same observability wiring as the API.
setup_logging(level=settings.log_level)
init_sentry(settings.sentry_dsn, settings.app_env)

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

# Explicitly import task modules (autodiscover looks for tasks.py by default).
celery.conf.update(
    include=[
        "ingestion.github",
        "ingestion.notion",
        "ingestion.embeddings",
    ],
)
