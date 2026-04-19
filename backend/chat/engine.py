"""Chat orchestration engine.

Handles intent detection, context retrieval, prompt construction,
and LLM response generation.

NOTE [B3 placeholder]: `SourceChunk` and `ChatEngineResult` are landed here
ahead of A11/A12 because B3 needs them to type-check and test against the
locked api-contract.md shapes. Track A owns the final location and any
non-contract fields. The `source_origin` field is the one B3-driven
addition pending A's sign-off (see B3 PR description and design doc
`docs/v1/planning/detailed/partner-b-b3-code-processor.md`).
"""

from dataclasses import dataclass, field


@dataclass
class SourceChunk:
    chunk_id: str
    document_id: str
    document_title: str
    file_path: str | None
    source: str  # "github" | "notion"
    url: str
    relevance_score: float
    content_preview: str


@dataclass
class ChatEngineResult:
    response_text: str
    sources: list[SourceChunk]
    conversation_id: str
    message_id: str
    intent: str  # "explain" | "generate" | "question"
    model: str
    input_tokens: int
    output_tokens: int
    # B3-proposed addition — A signs off in B3 PR review.
    # "code" | "docs" | "mixed" | None (None → B3 derives from sources).
    source_origin: str | None = field(default=None)
