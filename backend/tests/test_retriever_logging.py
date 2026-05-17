"""Lock the structured-logging contract for the retrieval layer.

Mocks the embedding model and the SQLAlchemy session so the tests don't
need a real DB or the sentence-transformers download. Asserts on log
records via caplog — fields are read off LogRecord directly (same pattern
as `test_usage_middleware.py`).
"""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge import retriever


@pytest.fixture
def stub_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_embed(query: str) -> list[float]:
        return [0.0] * 4

    monkeypatch.setattr(retriever, "_embed_query", _fake_embed)


def _fake_row(score: float = 0.91) -> Any:
    row = MagicMock()
    row.chunk_id = "11111111-1111-1111-1111-111111111111"
    row.document_id = "22222222-2222-2222-2222-222222222222"
    row.content = "some content"
    row.start_line = 1
    row.end_line = 5
    row.chunk_metadata = {}
    row.document_title = "doc"
    row.file_path = "foo.py"
    row.source = "github"
    row.url = "https://github.com/x/y/blob/main/foo.py"
    row.relevance_score = score
    return row


def _make_session(rows: list[Any]) -> Any:
    result = MagicMock()
    result.fetchall.return_value = rows
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _records(caplog: pytest.LogCaptureFixture, msg: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "knowledge.retriever" and r.getMessage() == msg]


@pytest.mark.asyncio
async def test_logs_start_and_completion_on_success(
    stub_embed: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="knowledge.retriever")
    session = _make_session([_fake_row(score=0.91), _fake_row(score=0.73)])

    chunks = await retriever.retrieve(
        query="how does auth work",
        user_id="user-1",
        session=session,
        top_k=5,
    )

    assert len(chunks) == 2

    start = _records(caplog, "retrieval_started")
    assert len(start) == 1
    assert start[0].query_len == len("how does auth work")
    assert start[0].user_id == "user-1"
    assert start[0].top_k == 5
    assert start[0].source_filter is None

    done = _records(caplog, "retrieval_completed")
    assert len(done) == 1
    assert done[0].chunk_count == 2
    assert done[0].top_score == pytest.approx(0.91)
    assert done[0].user_id == "user-1"


@pytest.mark.asyncio
async def test_logs_empty_result_with_null_top_score(
    stub_embed: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="knowledge.retriever")
    session = _make_session([])

    chunks = await retriever.retrieve(
        query="nothing matches this",
        user_id="user-1",
        session=session,
    )

    assert chunks == []
    done = _records(caplog, "retrieval_completed")
    assert len(done) == 1
    assert done[0].chunk_count == 0
    assert done[0].top_score is None


@pytest.mark.asyncio
async def test_logs_failure_and_reraises(
    stub_embed: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="knowledge.retriever")
    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db gone"))

    with pytest.raises(RuntimeError, match="db gone"):
        await retriever.retrieve(
            query="anything",
            user_id="user-1",
            session=session,
        )

    failures = _records(caplog, "retrieval_failed")
    assert len(failures) == 1
    assert failures[0].levelname == "ERROR"
    assert failures[0].user_id == "user-1"
    # Completion log must NOT fire on the failure path.
    assert _records(caplog, "retrieval_completed") == []


@pytest.mark.asyncio
async def test_honors_source_filter_in_log(
    stub_embed: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="knowledge.retriever")
    session = _make_session([])

    await retriever.retrieve(
        query="q",
        user_id="user-1",
        session=session,
        source_filter="notion",
    )

    start = _records(caplog, "retrieval_started")
    assert start[0].source_filter == "notion"
    done = _records(caplog, "retrieval_completed")
    assert done[0].source_filter == "notion"
