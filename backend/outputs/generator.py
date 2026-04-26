"""B2 — Output generator service.

Layer 3 (v1.5) per `docs/v1/planning/partner-b-v1-plan.md`.

Consumes a `ChatEngineResult` and produces a persisted `Output` row.
Called from `POST /outputs/generate` (B6b) in the v1.5 release cycle.

Design notes — "unclear defaults" flagged here per the pre-flight pass:

- **Q1 (signature):** `generate_output` takes `message_id` and fetches the
  chat result itself, on the assumption that Track A's `messages` table
  stores the full shape per `api-contract.md` §Database Tables. A's
  migration does NOT exist yet, so the internal fetch raises
  `NotImplementedError` for now. B6b can call `build_output(...)` directly
  with a pre-built `ChatEngineResult` if it needs to route around this
  before A ships.
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

from sqlalchemy.ext.asyncio import AsyncSession

from chat.engine import ChatEngineResult, SourceChunk
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
    # TODO [B2/A]: reconstruct `ChatEngineResult` from A's `messages` table
    # once it exists. Fields land per `api-contract.md` §Database Tables ->
    # messages: `sources` JSONB -> `list[SourceChunk]`, `content` ->
    # `response_text`, `intent` direct, `token_count` split across input/
    # output if A stores both. If A's stored shape doesn't carry enough to
    # reconstruct the full result, flip Q1 to (a): B6b passes a pre-built
    # `ChatEngineResult` directly into `build_output(...)` and we drop
    # this fetch.
    del session, message_id
    raise NotImplementedError(
        "Awaiting Track A's messages table. B6b may route around this by "
        "calling build_output(...) directly with a pre-built ChatEngineResult."
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
