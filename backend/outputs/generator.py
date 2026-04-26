"""B2 — Output generator service.

Layer 3 (v1.5) per `docs/v1/planning/partner-b-v1-plan.md`.

Consumes a `ChatEngineResult` and produces a persisted `Output` row.
Called from `POST /outputs/generate` (B6b) in the v1.5 release cycle.

Design notes — "unclear defaults" flagged here per the pre-flight pass:

- **Q1 (signature):** `generate_output` takes `message_id` and fetches the
  chat result from A's `messages` table. `model` isn't persisted there;
  `build_output` doesn't use it.
- **Q2 (intent vs output_type):** request's `output_type` is authoritative.
  No cross-check against `result.intent`. If a user asks for a
  `code_snippet` on an `explain`-intent message, we honor it and derive
  from whatever fenced code exists in `response_text`.
- **Q3 (no LLM):** title / language / file_path are heuristic only. No
  extra Anthropic calls. Upgrade to LLM-polished titles is a v2 concern.
- **Q6 (title heuristics):** first heading or first non-empty line; falls
  back to a generic label per `output_type`. Good enough, may look
  mediocre on some responses — revisit if users flag.
- **Q7 (idempotency):** every call creates a new row. No unique index on
  `(message_id, type)`. Repeated calls accumulate rows — matches the 201
  Created contract but will surprise anyone expecting dedup.
"""

from __future__ import annotations

import re
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.engine import ChatEngineResult, SourceChunk
from models.message import Message
from models.output import Output

_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", re.DOTALL)
_VALID_TYPES: Final[frozenset[str]] = frozenset({"code_snippet", "summary", "report"})
_TITLE_MAX = 500
_FALLBACK_TITLES: Final[dict[str, str]] = {
    "code_snippet": "Code snippet",
    "summary": "Summary",
    "report": "Report",
}


def build_output(
    result: ChatEngineResult, output_type: str, user_id: uuid.UUID
) -> Output:
    """Pure function: `ChatEngineResult` -> unsaved `Output` row.

    Isolated from the DB so the heuristics are trivially unit-testable.
    The async wrapper `generate_output` composes this with a session read
    + `session.add` + flush.
    """
    if output_type not in _VALID_TYPES:
        raise ValueError(f"Unknown output_type: {output_type!r}")
    if not result.response_text.strip():
        raise ValueError("response_text is empty")

    content, language = _derive_content_and_language(result.response_text, output_type)
    title = _derive_title(result.response_text, output_type)
    file_path_suggestion = (
        _derive_file_path(result.sources) if output_type == "code_snippet" else None
    )

    metadata = {
        "language": language,
        "file_path_suggestion": file_path_suggestion,
        "source_message_id": result.message_id,
        "source_conversation_id": result.conversation_id,
    }

    return Output(
        user_id=user_id,
        message_id=uuid.UUID(result.message_id),
        conversation_id=uuid.UUID(result.conversation_id),
        type=output_type,
        title=title,
        content=content,
        output_metadata=metadata,
    )


async def generate_output(
    session: AsyncSession,
    user_id: uuid.UUID,
    message_id: str,
    output_type: str,
) -> Output:
    """Service entry point used by B6b's /outputs/generate route."""
    result = await _fetch_chat_result(session, message_id)
    output = build_output(result, output_type, user_id)
    session.add(output)
    await session.flush()
    return output


async def _fetch_chat_result(session: AsyncSession, message_id: str) -> ChatEngineResult:
    """Reconstruct a `ChatEngineResult` from A's `messages` table.

    Only assistant rows are eligible. `model` is not persisted in `messages`,
    so we pass through an empty string — downstream `build_output` doesn't
    use it. `sources` JSONB is rehydrated into `SourceChunk` dataclasses.
    """
    msg = (
        await session.execute(select(Message).where(Message.id == uuid.UUID(message_id)))
    ).scalar_one_or_none()
    if msg is None:
        raise ValueError(f"Message {message_id} not found")
    if msg.role != "assistant":
        raise ValueError(f"Message {message_id} is not an assistant message")

    sources = [
        SourceChunk(
            chunk_id=s.get("chunk_id", ""),
            document_id=s.get("document_id", ""),
            document_title=s.get("document_title", ""),
            file_path=s.get("file_path"),
            source=s.get("source", ""),
            url=s.get("url", ""),
            relevance_score=float(s.get("relevance_score", 0.0)),
            content_preview=s.get("content_preview", ""),
        )
        for s in (msg.sources or [])
    ]

    return ChatEngineResult(
        response_text=msg.content,
        sources=sources,
        conversation_id=str(msg.conversation_id),
        message_id=str(msg.id),
        intent=msg.intent or "question",
        model="",
        input_tokens=msg.input_tokens or 0,
        output_tokens=msg.output_tokens or 0,
    )


def _derive_content_and_language(
    response_text: str, output_type: str
) -> tuple[str, str | None]:
    if output_type != "code_snippet":
        return response_text, None
    matches = _FENCE_RE.findall(response_text)
    if not matches:
        # No fenced block -- fall back to full text, language unknown.
        return response_text, None
    lang, code = max(matches, key=lambda m: len(m[1]))
    return code.strip(), (lang.strip() or None)


def _derive_title(response_text: str, output_type: str) -> str:
    in_fence = False
    for raw in response_text.strip().splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
            if not line:
                continue
        return line[:_TITLE_MAX]
    return _FALLBACK_TITLES[output_type]


def _derive_file_path(sources: list[SourceChunk]) -> str | None:
    for s in sorted(sources, key=lambda c: c.relevance_score, reverse=True):
        if s.file_path:
            return s.file_path
    return None
