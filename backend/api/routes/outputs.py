"""B6b — `/outputs/*` route layer.

Layer 3 (v1.5) per `docs/v1/planning/partner-b-v1-plan.md`. Stubbed in
v1 so the contract shapes compile but the router is NOT wired into
`main.py` — layer-2 hiding rule.

Shapes copied verbatim from `docs/api-contract.md` §Outputs.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class OutputMetadata(BaseModel):
    language: str | None = None
    file_path_suggestion: str | None = None
    source_message_id: str
    source_conversation_id: str


class GenerateOutputRequest(BaseModel):
    message_id: str
    output_type: str  # "code_snippet" | "summary" | "report"


class OutputResponse(BaseModel):
    id: str
    type: str
    title: str
    content: str
    metadata: OutputMetadata
    created_at: str


class OutputListItem(BaseModel):
    id: str
    type: str
    title: str
    preview: str
    created_at: str


class OutputListResponse(BaseModel):
    outputs: list[OutputListItem]
    total: int
    page: int


@router.post("/generate", response_model=OutputResponse, status_code=201)
async def generate_output(request: GenerateOutputRequest) -> OutputResponse:
    # TODO [B6b]: call B2 generator, persist via B1 model, return shape.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="B6b not implemented")


@router.get("", response_model=OutputListResponse)
async def list_outputs(type: str | None = None, page: int = 1, limit: int = 20) -> OutputListResponse:
    # TODO [B7]: paginate (default 20, max 100), optional ?type= filter.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="B7 not implemented")


@router.get("/{output_id}", response_model=OutputResponse)
async def get_output(output_id: str) -> OutputResponse:
    # TODO [B6b]: load by id, 404 if missing or wrong user.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="B6b not implemented")
