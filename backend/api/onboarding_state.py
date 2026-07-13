"""Writers for `memberships.onboarding_state` (roadmap F3 follow-up).

The dashboard renders three badges from this column — needs-setup (NULL),
"indexing", "ready" — and routes "ready" workspaces into the chat shell.
Until now nothing ever wrote the column, so every workspace re-entry landed
on /onboarding forever. State machine:

    NULL/"indexing"  --ingest kicked off-->  "indexing"
    any              --first ingest job completes-->  "ready"

"ready" is terminal: a later re-index sets neither back.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ingest_job import IngestJob
from models.membership import Membership

logger = logging.getLogger(__name__)

READY = "ready"
INDEXING = "indexing"


async def mark_indexing(
    session: AsyncSession, user_id: uuid.UUID, team_id: uuid.UUID
) -> None:
    """Record that this member's workspace has an ingest in flight.

    No-op once "ready" — a re-index must not regress the dashboard badge.
    """
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user_id, Membership.team_id == team_id
            )
        )
    ).scalar_one_or_none()
    if membership is not None and membership.onboarding_state != READY:
        membership.onboarding_state = INDEXING


def mark_ready_sync(session, job_id: uuid.UUID) -> None:  # type: ignore[no-untyped-def]
    """Flip the job initiator's membership to "ready" (celery, sync session).

    Called wherever an ingest job reaches status="complete". Never raises:
    onboarding-state bookkeeping must not fail a finished ingest.
    """
    try:
        job = session.execute(
            select(IngestJob).where(IngestJob.id == job_id)
        ).scalar_one_or_none()
        if job is None or job.team_id is None:
            return
        membership = session.execute(
            select(Membership).where(
                Membership.user_id == job.user_id,
                Membership.team_id == job.team_id,
            )
        ).scalar_one_or_none()
        if membership is not None and membership.onboarding_state != READY:
            membership.onboarding_state = READY
            session.commit()
    except Exception:
        logger.exception("Failed to mark onboarding ready for job %s", job_id)
