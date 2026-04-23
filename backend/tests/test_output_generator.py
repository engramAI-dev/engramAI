"""B2 — output generator tests.

Hermetic. All tests drive `build_output` (pure function) so no DB fixture
is needed. Integration tests against a real Postgres + Track A's
`messages` table are DEFERRED until A's migration lands and the service-
level `generate_output` can actually fetch.
"""

from __future__ import annotations

import uuid

import pytest

from chat.engine import ChatEngineResult, SourceChunk
from outputs.generator import build_output, generate_output

_USER_ID = uuid.uuid4()
_MSG_ID = str(uuid.uuid4())
_CONV_ID = str(uuid.uuid4())


def _result(
    *,
    response_text: str = "hello",
    sources: list[SourceChunk] | None = None,
    intent: str = "explain",
) -> ChatEngineResult:
    return ChatEngineResult(
        response_text=response_text,
        sources=sources or [],
        conversation_id=_CONV_ID,
        message_id=_MSG_ID,
        intent=intent,
        model="claude-sonnet-4",
        input_tokens=10,
        output_tokens=20,
    )


def _source(
    *, file_path: str | None = None, score: float = 0.5, source: str = "github"
) -> SourceChunk:
    return SourceChunk(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title="doc",
        file_path=file_path,
        source=source,
        url="https://example.test",
        relevance_score=score,
        content_preview="preview",
    )


# ---------- content + language ----------


def test_code_snippet_extracts_fenced_block_and_language() -> None:
    text = "Here is the code:\n\n```python\ndef f():\n    return 1\n```\n"
    out = build_output(_result(response_text=text, intent="generate"), "code_snippet", _USER_ID)
    assert out.content == "def f():\n    return 1"
    assert out.output_metadata["language"] == "python"


def test_code_snippet_picks_longest_fence_when_multiple() -> None:
    text = (
        "```bash\nls\n```\n"
        "```python\ndef handler():\n    return {'ok': True}\n```\n"
    )
    out = build_output(_result(response_text=text, intent="generate"), "code_snippet", _USER_ID)
    assert "def handler" in out.content
    assert out.output_metadata["language"] == "python"


def test_code_snippet_no_fence_falls_back_to_full_text_and_none_language() -> None:
    text = "Just prose, no fenced block."
    out = build_output(_result(response_text=text), "code_snippet", _USER_ID)
    assert out.content == text
    assert out.output_metadata["language"] is None


def test_code_snippet_empty_fence_tag_yields_none_language() -> None:
    text = "```\nraw code\n```"
    out = build_output(_result(response_text=text), "code_snippet", _USER_ID)
    assert out.content == "raw code"
    assert out.output_metadata["language"] is None


def test_summary_passes_content_through_and_no_language() -> None:
    text = "# Overview\n\nThe auth flow is..."
    out = build_output(_result(response_text=text), "summary", _USER_ID)
    assert out.content == text
    assert out.output_metadata["language"] is None


def test_report_passes_content_through() -> None:
    text = "## Findings\n\nThree bugs identified."
    out = build_output(_result(response_text=text), "report", _USER_ID)
    assert out.content == text
    assert out.output_metadata["language"] is None


# ---------- title ----------


def test_title_from_first_heading() -> None:
    text = "# Auth middleware implementation\n\nDetails..."
    out = build_output(_result(response_text=text), "summary", _USER_ID)
    assert out.title == "Auth middleware implementation"


def test_title_from_first_non_empty_line_when_no_heading() -> None:
    text = "\n\nAuth handler notes\n\nDetails..."
    out = build_output(_result(response_text=text), "summary", _USER_ID)
    assert out.title == "Auth handler notes"


def test_title_skips_fenced_content_to_find_prose() -> None:
    text = "```python\nx = 1\n```\nAfter the code\n"
    out = build_output(_result(response_text=text, intent="generate"), "code_snippet", _USER_ID)
    assert out.title == "After the code"


def test_title_prose_before_fence_wins_over_prose_after() -> None:
    text = "Here's the implementation:\n\n```python\ndef f(): ...\n```\n\nThat's it.\n"
    out = build_output(_result(response_text=text, intent="generate"), "code_snippet", _USER_ID)
    assert out.title == "Here's the implementation:"


def test_title_falls_back_to_generic_for_each_type() -> None:
    # All-whitespace response_text is rejected by validation — use a response
    # that contains ONLY fenced content so the heuristic scanner finds nothing.
    text = "```\n\n```"
    out = build_output(_result(response_text=text), "code_snippet", _USER_ID)
    assert out.title == "Code snippet"


def test_title_truncated_to_column_limit() -> None:
    text = "x" * 1200
    out = build_output(_result(response_text=text), "report", _USER_ID)
    assert len(out.title) == 500


# ---------- file_path_suggestion ----------


def test_file_path_picks_highest_score_source() -> None:
    sources = [
        _source(file_path="a/low.py", score=0.1),
        _source(file_path="b/high.py", score=0.9),
        _source(file_path=None, score=0.99),  # top relevance but no path
    ]
    text = "```python\ncode\n```"
    out = build_output(
        _result(response_text=text, sources=sources, intent="generate"),
        "code_snippet",
        _USER_ID,
    )
    assert out.output_metadata["file_path_suggestion"] == "b/high.py"


def test_file_path_none_when_no_sources_have_paths() -> None:
    sources = [_source(file_path=None, score=0.9)]
    text = "```python\ncode\n```"
    out = build_output(
        _result(response_text=text, sources=sources, intent="generate"),
        "code_snippet",
        _USER_ID,
    )
    assert out.output_metadata["file_path_suggestion"] is None


def test_file_path_none_for_non_code_outputs() -> None:
    sources = [_source(file_path="docs/x.md", score=0.9)]
    out = build_output(_result(sources=sources), "summary", _USER_ID)
    assert out.output_metadata["file_path_suggestion"] is None


# ---------- metadata + identity ----------


def test_metadata_includes_source_ids() -> None:
    out = build_output(_result(), "summary", _USER_ID)
    assert out.output_metadata["source_message_id"] == _MSG_ID
    assert out.output_metadata["source_conversation_id"] == _CONV_ID


def test_output_carries_user_and_uuid_fks() -> None:
    out = build_output(_result(), "summary", _USER_ID)
    assert out.user_id == _USER_ID
    assert out.message_id == uuid.UUID(_MSG_ID)
    assert out.conversation_id == uuid.UUID(_CONV_ID)
    assert out.type == "summary"


# ---------- validation ----------


def test_unknown_output_type_raises() -> None:
    with pytest.raises(ValueError, match="Unknown output_type"):
        build_output(_result(), "unknown", _USER_ID)


def test_empty_response_text_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        build_output(_result(response_text="   "), "summary", _USER_ID)


# ---------- async wrapper ----------


@pytest.mark.asyncio
async def test_generate_output_blocked_on_partner_a_fetch() -> None:
    # Documents the current state: service-level entry point is gated on A's
    # messages table. Flag a regression if someone silently swaps the fetch.
    with pytest.raises(NotImplementedError, match="messages table"):
        await generate_output(session=None, user_id=_USER_ID, message_id=_MSG_ID, output_type="summary")  # type: ignore[arg-type]
