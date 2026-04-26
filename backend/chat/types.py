"""Shared types for the chat/knowledge layer.

Extracted to break the circular import between engine.py and retriever.py.
Both SourceChunk and ChatEngineResult are part of the locked B contract.
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
