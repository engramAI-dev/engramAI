"""Onboarding-state writer tests — hermetic, no DB.

Covers the two writers for `memberships.onboarding_state` (F3 follow-up):
`mark_indexing` at ingest kickoff and `mark_ready_sync` at job completion.
Fake sessions pop queued results per execute() call, in issue order.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from api.onboarding_state import mark_indexing, mark_ready_sync
from models.ingest_job import IngestJob
from models.membership import Membership

USER_ID = uuid.uuid4()
TEAM_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeSyncSession:
    def __init__(self, results: list[Any]) -> None:
        self.results = list(results)
        self.committed = False

    def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self.results.pop(0))

    def commit(self) -> None:
        self.committed = True


class _FakeAsyncSession:
    def __init__(self, results: list[Any]) -> None:
        self.results = list(results)

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self.results.pop(0))


def _membership(state: str | None) -> Membership:
    return Membership(
        id=uuid.uuid4(), team_id=TEAM_ID, user_id=USER_ID, onboarding_state=state
    )


def _job(team_id: uuid.UUID | None = TEAM_ID) -> IngestJob:
    return IngestJob(
        id=JOB_ID,
        user_id=USER_ID,
        team_id=team_id,
        source="github",
        source_url="https://github.com/o/r",
        status="complete",
    )


# ---------------------------------------------------------------------------
# mark_ready_sync — celery-side completion writer
# ---------------------------------------------------------------------------


def test_ready_set_on_completion() -> None:
    membership = _membership(state="indexing")
    session = _FakeSyncSession([_job(), membership])
    mark_ready_sync(session, JOB_ID)
    assert membership.onboarding_state == "ready"
    assert session.committed


def test_ready_skips_team_less_job() -> None:
    session = _FakeSyncSession([_job(team_id=None)])
    mark_ready_sync(session, JOB_ID)
    assert not session.committed


def test_ready_never_raises() -> None:
    class _Broken:
        def execute(self, stmt: Any) -> Any:
            raise RuntimeError("db down")

    # Bookkeeping must not fail a finished ingest.
    mark_ready_sync(_Broken(), JOB_ID)


# ---------------------------------------------------------------------------
# mark_indexing — kickoff writer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_indexing_set_from_null() -> None:
    membership = _membership(state=None)
    await mark_indexing(_FakeAsyncSession([membership]), USER_ID, TEAM_ID)
    assert membership.onboarding_state == "indexing"


@pytest.mark.asyncio
async def test_indexing_does_not_regress_ready() -> None:
    membership = _membership(state="ready")
    await mark_indexing(_FakeAsyncSession([membership]), USER_ID, TEAM_ID)
    assert membership.onboarding_state == "ready"
