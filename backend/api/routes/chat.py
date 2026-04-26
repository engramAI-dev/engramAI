"""A13 — Chat API endpoint with SSE streaming.

Design: D35 (manual StreamingResponse), D36 (user msg before, assistant after).
Sets request.state.usage for B13's usage tracking middleware.
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from chat.engine import chat_engine
from models.conversation import Conversation
from models.database import get_session
from models.message import Message

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/")
async def send_message(
    chat_request: ChatRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Send a message and get a streaming AI response grounded in indexed knowledge."""

    async def sse_generator():  # type: ignore[no-untyped-def]
        result = None
        try:
            async for event in chat_engine.process_stream(
                message=chat_request.message,
                user_id=user.id,
                session=session,
                conversation_id=chat_request.conversation_id,
            ):
                if event["type"] == "done":
                    # Capture result for usage tracking
                    result = event.get("result")
                    # Send done event without the internal result object
                    done_event = {
                        "type": "done",
                        "conversation_id": event["conversation_id"],
                        "message_id": event["message_id"],
                    }
                    yield f"data: {json.dumps(done_event)}\n\n"
                else:
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            logger.exception("Chat stream error")
            error_event = {"type": "error", "content": "An error occurred while generating the response."}
            yield f"data: {json.dumps(error_event)}\n\n"

        # Set usage for B13's middleware (after stream completes)
        if result:
            request.state.usage = {
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    message_count: int
    updated_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int
    page: int


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationListResponse:
    """List user's conversations."""
    uid = uuid.UUID(user.id)
    offset = (page - 1) * limit

    # Get total count
    count_result = await session.execute(
        select(func.count(Conversation.id)).where(Conversation.user_id == uid)
    )
    total = count_result.scalar_one()

    # Get conversations with message counts
    stmt = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.updated_at,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == uid)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=str(row.id),
                title=row.title,
                message_count=row.message_count,
                updated_at=row.updated_at.isoformat() if row.updated_at else "",
            )
            for row in rows
        ],
        total=total,
        page=page,
    )


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict] = []
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageListResponse:
    """Get messages for a conversation."""
    uid = uuid.UUID(user.id)
    conv_id = uuid.UUID(conversation_id)

    # Verify conversation belongs to user
    conv_result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == uid,
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get messages
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    return MessageListResponse(
        messages=[
            MessageResponse(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                sources=msg.sources if isinstance(msg.sources, list) else [],
                created_at=msg.created_at.isoformat() if msg.created_at else "",
            )
            for msg in messages
        ]
    )
