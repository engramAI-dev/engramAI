"""A12 — Chat orchestration engine.

Design: D32 (keyword intent detection), D33 (system + XML context),
D34 (last 10 messages).

NOTE [B3 placeholder]: `SourceChunk` and `ChatEngineResult` are landed here
ahead of A11/A12 because B3 needs them to type-check and test against the
locked api-contract.md shapes. Partner A owns the final location and any
non-contract fields. The `source_origin` field is the one B3-driven
addition pending A's sign-off (see B3 PR description and design doc
`docs/v1/planning/detailed/partner-b-b3-code-processor.md`).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.llm import llm_client
from chat.types import ChatEngineResult, SourceChunk  # noqa: F401 — re-export for B's imports
from knowledge.retriever import retrieve
from models.conversation import Conversation
from models.message import Message

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 10  # D34: last 10 messages

_SYSTEM_PROMPT = """You are Engram, an engineering intelligence assistant. You help engineers \
understand codebases and write code grounded in verified organizational knowledge.

Rules:
- Base your answers ONLY on the provided context. If the context doesn't contain \
enough information, say so clearly.
- When referencing code, cite the source file path and line numbers.
- When generating code, match the style and conventions visible in the context.
- Be concise and precise. Engineers value accuracy over verbosity."""

_GENERATE_ADDENDUM = """
The user is asking you to generate code. Write clean, production-ready code that \
matches the patterns in the context. Include necessary imports and type hints."""

_EXPLAIN_ADDENDUM = """
The user is asking for an explanation. Be thorough but concise. Reference specific \
files and functions from the context."""


def detect_intent(message: str) -> str:
    """Keyword-based intent detection (D32)."""
    msg = message.lower()
    generate_keywords = [
        "write", "create", "generate", "implement", "build", "make a",
        "add a", "code for", "function that", "class that", "script",
    ]
    explain_keywords = [
        "explain", "what does", "how does", "why does", "what is",
        "walk me through", "describe", "tell me about", "how is",
        "what are", "why is",
    ]

    # Check generate first (more specific)
    if any(kw in msg for kw in generate_keywords):
        return "generate"
    if any(kw in msg for kw in explain_keywords):
        return "explain"
    return "question"


def _format_context(sources: list[SourceChunk]) -> str:
    """Format retrieved chunks as XML-tagged context for the prompt (D33)."""
    if not sources:
        return "<context>\nNo relevant context found.\n</context>"

    parts: list[str] = ["<context>"]
    for i, chunk in enumerate(sources, 1):
        source_label = f"[{chunk.source}]"
        path_label = f" {chunk.file_path}" if chunk.file_path else ""
        parts.append(f"<source id=\"{i}\" {source_label}{path_label} relevance=\"{chunk.relevance_score}\">")
        parts.append(chunk.content_preview)
        parts.append("</source>")
    parts.append("</context>")
    return "\n".join(parts)


async def _load_history(
    session: AsyncSession,
    conversation_id: str,
) -> list[dict[str, str]]:
    """Load last N messages for conversation history (D34)."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # chronological order

    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]


class ChatEngine:
    """Orchestrates intent detection, retrieval, prompt construction, and LLM streaming."""

    async def process_stream(
        self,
        message: str,
        user_id: str,
        team_id: str,
        session: AsyncSession,
        conversation_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """Process a chat message with streaming.

        Yields dicts with SSE event structure:
          {"type": "text", "content": "..."}
          {"type": "sources", "content": [...]}
          {"type": "done", "conversation_id": "...", "message_id": "...",
           "result": ChatEngineResult}
        """
        # 1. Detect intent (D32)
        intent = detect_intent(message)
        logger.info(
            "intent_detected",
            extra={
                "intent": intent,
                "user_id": user_id,
                "query_len": len(message),
            },
        )

        # 2. Retrieve context (A9)
        sources = await retrieve(
            query=message,
            user_id=user_id,
            team_id=team_id,
            session=session,
            top_k=10,
        )

        if not sources:
            # The user will get "I don't know" or a low-confidence answer.
            # Logging this lets us correlate empty-context replies post-hoc.
            logger.warning(
                "answering_without_context",
                extra={
                    "intent": intent,
                    "user_id": user_id,
                    "query_len": len(message),
                },
            )

        # 3. Get or create conversation
        if conversation_id:
            conv_id = uuid.UUID(conversation_id)
        else:
            conv = Conversation(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                team_id=uuid.UUID(team_id),
                title=message[:100],
            )
            session.add(conv)
            await session.flush()
            conv_id = conv.id

        # 4. Store user message (D36: before streaming)
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user",
            content=message,
        )
        session.add(user_msg)
        await session.flush()

        # 5. Build prompt (D33: system + XML context in user message)
        system = _SYSTEM_PROMPT
        if intent == "generate":
            system += _GENERATE_ADDENDUM
        elif intent == "explain":
            system += _EXPLAIN_ADDENDUM

        context_text = _format_context(sources)

        # Load conversation history (D34)
        history: list[dict[str, str]] = []
        if conversation_id:
            history = await _load_history(session, conversation_id)

        messages = [
            *history,
            {"role": "user", "content": f"{context_text}\n\n{message}"},
        ]

        # 6. Stream LLM response
        response_text = ""
        input_tokens = 0
        output_tokens = 0
        model = ""
        assistant_msg_id = uuid.uuid4()

        async for event in llm_client.stream(system=system, messages=messages):
            if event.type == "text_delta":
                response_text += event.text
                yield {"type": "text", "content": event.text}
            elif event.type == "complete":
                input_tokens = event.input_tokens
                output_tokens = event.output_tokens
                model = settings.llm_model

        # 7. Yield sources
        yield {
            "type": "sources",
            "content": [
                {
                    "chunk_id": s.chunk_id,
                    "document_id": s.document_id,
                    "document_title": s.document_title,
                    "file_path": s.file_path,
                    "source": s.source,
                    "url": s.url,
                    "relevance_score": s.relevance_score,
                    "content_preview": s.content_preview,
                }
                for s in sources
            ],
        }

        # 8. Store assistant message (D36: after streaming)
        assistant_msg = Message(
            id=assistant_msg_id,
            conversation_id=conv_id,
            role="assistant",
            content=response_text,
            sources=[
                {
                    "chunk_id": s.chunk_id,
                    "document_id": s.document_id,
                    "document_title": s.document_title,
                    "file_path": s.file_path,
                    "source": s.source,
                    "url": s.url,
                    "relevance_score": s.relevance_score,
                    "content_preview": s.content_preview,
                }
                for s in sources
            ],
            intent=intent,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        session.add(assistant_msg)
        await session.commit()

        # 9. Build and yield final result
        result = ChatEngineResult(
            response_text=response_text,
            sources=sources,
            conversation_id=str(conv_id),
            message_id=str(assistant_msg_id),
            intent=intent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        yield {
            "type": "done",
            "conversation_id": str(conv_id),
            "message_id": str(assistant_msg_id),
            "result": result,
        }


# Module-level instance
from config import settings  # noqa: E402

chat_engine = ChatEngine()
