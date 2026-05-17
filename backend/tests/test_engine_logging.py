"""Lock the structured-logging contract for the chat engine.

Two signals matter most for post-launch debuggability:
- `intent_detected` so we can correlate intent against answer quality
- `answering_without_context` (WARNING) when retrieval returned 0 chunks
  but the engine still proceeded — i.e. the user is about to get
  "I don't know" or a low-confidence reply

Both are tested via `process_stream` with `retrieve`, `llm_client`, and
the SQLAlchemy session mocked. No DB or LLM access.
"""

import logging
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat import engine as engine_mod
from chat.llm import StreamEvent


async def _empty_stream(*_: Any, **__: Any):
    yield StreamEvent(type="text_delta", text="I don't know.")
    yield StreamEvent(type="complete", text="", input_tokens=5, output_tokens=3)


@pytest.fixture
def mock_session() -> Any:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def patched_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub retrieve to return [] and llm_client.stream to a fixed event sequence."""
    async def _fake_retrieve(**kwargs: Any) -> list:  # noqa: ARG001
        return []

    monkeypatch.setattr(engine_mod, "retrieve", _fake_retrieve)
    monkeypatch.setattr(engine_mod.llm_client, "stream", _empty_stream)


@pytest.mark.asyncio
async def test_logs_intent_detection(
    mock_session: Any,
    patched_engine: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="chat.engine")

    user_id = str(uuid.uuid4())
    events = []
    async for evt in engine_mod.chat_engine.process_stream(
        message="explain how auth works",
        user_id=user_id,
        session=mock_session,
    ):
        events.append(evt)

    intent_records = [
        r for r in caplog.records
        if r.name == "chat.engine" and r.getMessage() == "intent_detected"
    ]
    assert len(intent_records) == 1
    assert intent_records[0].intent == "explain"
    assert intent_records[0].user_id == user_id
    assert intent_records[0].query_len == len("explain how auth works")


@pytest.mark.asyncio
async def test_warns_when_answering_without_context(
    mock_session: Any,
    patched_engine: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="chat.engine")

    user_id = str(uuid.uuid4())
    async for _ in engine_mod.chat_engine.process_stream(
        message="something not in the corpus",
        user_id=user_id,
        session=mock_session,
    ):
        pass

    warnings = [
        r for r in caplog.records
        if r.name == "chat.engine" and r.getMessage() == "answering_without_context"
    ]
    assert len(warnings) == 1
    assert warnings[0].levelname == "WARNING"
    assert warnings[0].user_id == user_id
    assert warnings[0].intent in {"explain", "generate", "question"}


@pytest.mark.asyncio
async def test_no_empty_context_warning_when_sources_present(
    mock_session: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Inverse case: when retrieve returns chunks, no warning fires."""
    from chat.types import SourceChunk

    async def _fake_retrieve(**kwargs: Any) -> list:  # noqa: ARG001
        return [
            SourceChunk(
                chunk_id="c1",
                document_id="d1",
                document_title="t",
                file_path="a.py",
                source="github",
                url="https://example/a.py",
                relevance_score=0.8,
                content_preview="x",
            )
        ]

    monkeypatch.setattr(engine_mod, "retrieve", _fake_retrieve)
    monkeypatch.setattr(engine_mod.llm_client, "stream", _empty_stream)
    caplog.set_level(logging.WARNING, logger="chat.engine")

    async for _ in engine_mod.chat_engine.process_stream(
        message="explain auth",
        user_id=str(uuid.uuid4()),
        session=mock_session,
    ):
        pass

    warnings = [
        r for r in caplog.records
        if r.name == "chat.engine" and r.getMessage() == "answering_without_context"
    ]
    assert warnings == []
