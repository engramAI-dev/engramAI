from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    sources: list[dict[str, str]]


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest) -> ChatResponse:
    """Send a message and get an AI response grounded in indexed knowledge."""
    # TODO: Intent detection → retrieval → LLM call → response
    return ChatResponse(
        response="not implemented",
        conversation_id=request.conversation_id or "new",
        sources=[],
    )
