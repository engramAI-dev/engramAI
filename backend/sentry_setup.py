"""Sentry initialization shared by the API process (main.py) and the
Celery worker process (celery_app.py).

Both integrations are registered in both processes — the FastAPI integration
is a no-op when there's no ASGI app (worker), and the Celery integration is
a no-op when there are no tasks (api). This keeps the init call identical.

Gated on dsn being non-empty so dev / test environments without a DSN
are silently no-op rather than emitting errors.
"""

from __future__ import annotations

import os

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration


def init_sentry(dsn: str, environment: str) -> bool:
    """Initialize Sentry. Returns True if initialized, False if skipped."""
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        send_default_pii=False,
        environment=environment,
        release=os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev"),
    )
    return True
