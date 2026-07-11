"""B6b/B7 — `/outputs/*` route layer.

Layer 3 (v1.5) per `docs/v1/planning/partner-b-v1-plan.md`. Wired into
`main.py` as of B9: the frontend history view consumes `GET /outputs`
and `GET /outputs/{id}`.

Shapes pulled verbatim from `docs/api-contract.md` §Outputs.

`POST /generate` reads A's `messages` table to reconstruct the chat
result, then persists an `Output` row.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from api.workspace import get_active_team_id
from models.database import get_session
from models.output import Output
from outputs.generator import generate_output

router = APIRouter()

OutputType = Literal["code_snippet", "summary", "report"]
_PREVIEW_LEN = 200


class OutputMetadata(BaseModel):
    language: str | None = None
    file_path_suggestion: str | None = None
    source_message_id: str
    source_conversation_id: str


class GenerateOutputRequest(BaseModel):
    message_id: str
    output_type: OutputType


class OutputResponse(BaseModel):
    id: uuid.UUID
    type: OutputType
    title: str
    content: str
    metadata: OutputMetadata
    created_at: datetime


class OutputListItem(BaseModel):
    id: uuid.UUID
    type: OutputType
    title: str
    preview: str
    created_at: datetime


class OutputListResponse(BaseModel):
    outputs: list[OutputListItem]
    total: int
    page: int


def _to_response(output: Output) -> OutputResponse:
    md = output.output_metadata or {}
    return OutputResponse(
        id=output.id,
        type=output.type,  # type: ignore[arg-type]
        title=output.title,
        content=output.content,
        metadata=OutputMetadata(
            language=md.get("language"),
            file_path_suggestion=md.get("file_path_suggestion"),
            source_message_id=md.get("source_message_id", ""),
            source_conversation_id=md.get("source_conversation_id", ""),
        ),
        created_at=output.created_at,
    )


@router.post("/generate", response_model=OutputResponse, status_code=status.HTTP_201_CREATED)
async def post_generate(
    body: GenerateOutputRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    team_id: Annotated[uuid.UUID, Depends(get_active_team_id)],
) -> OutputResponse:
    try:
        output = await generate_output(
            session=session,
            user_id=uuid.UUID(user.id),
            team_id=team_id,
            message_id=body.message_id,
            output_type=body.output_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    await session.commit()
    await session.refresh(output)
    return _to_response(output)


@router.get("", response_model=OutputListResponse)
async def list_outputs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    team_id: Annotated[uuid.UUID, Depends(get_active_team_id)],
    type: Annotated[OutputType | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OutputListResponse:
    user_uuid = uuid.UUID(user.id)
    where = [Output.user_id == user_uuid, Output.team_id == team_id]
    if type is not None:
        where.append(Output.type == type)

    total_stmt = select(func.count()).select_from(Output).where(*where)
    total = (await session.execute(total_stmt)).scalar_one()

    list_stmt = (
        select(Output)
        .where(*where)
        .order_by(Output.created_at.desc(), Output.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = (await session.execute(list_stmt)).scalars().all()

    return OutputListResponse(
        outputs=[
            OutputListItem(
                id=row.id,
                type=row.type,  # type: ignore[arg-type]
                title=row.title,
                preview=row.content[:_PREVIEW_LEN],
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
    )


@router.get("/{output_id}", response_model=OutputResponse)
async def get_output(
    output_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OutputResponse:
    stmt = select(Output).where(
        Output.id == output_id, Output.user_id == uuid.UUID(user.id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Output not found"
        )
    return _to_response(row)
