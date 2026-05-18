"""A4 — Celery application setup.

Importable standalone — does NOT import the FastAPI app (no circular deps).
Uses Redis broker from settings.
"""

import ssl

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
    # Silence the Celery 6 deprecation warning and keep startup retries on
    # if the broker is briefly unreachable during deploy.
    broker_connection_retry_on_startup=True,
    # managed Redis free tier caps at 500k commands/day. Default kombu Redis
    # transport polls BRPOP every ~0.1s (≈864k cmd/day idle), which alone
    # blows the cap and crashes the worker with ResponseError on the
    # restore_visible mutex. Slow the poll to 1s; keep visibility timeout
    # at the kombu default (3600s, plenty for our longest task).
    # See docs/v1/planning/detailed/2026-04-30-lane-5-deployment.md § 2.5.
    broker_transport_options={
        "polling_interval": 1.0,
        "visibility_timeout": 3600,
    },
    # Single worker replica has no peers — the remote-control fanout
    # channel is pure overhead. Disabling it is belt-and-suspenders with
    # --without-gossip on the start command.
    worker_enable_remote_control=False,
)

# Validate the TLS chain when the broker URL uses rediss:// (managed Redis + most
# managed providers). Without this, kombu warns "Secure redis scheme specified
# (rediss) with no ssl options, defaulting to insecure SSL behaviour" and
# skips chain validation. CERT_REQUIRED uses the system trust store; managed Redis
# uses a public CA so no ssl_ca_certs override needed. Plain redis:// dev
# URLs skip this entirely so local dev keeps working.
if settings.redis_url.startswith("rediss://"):
    celery.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

# Explicitly import task modules (autodiscover looks for tasks.py by default).
celery.conf.update(
    include=[
        "ingestion.github",
        "ingestion.notion",
        "ingestion.embeddings",
    ],
)
