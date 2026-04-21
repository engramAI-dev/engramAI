"""Knowledge store search endpoint.

Contract addition for B14 — see `docs/api-contract.md` §"Knowledge".
The endpoint is introduced here as a stub returning an empty chunk list
so the MCP plugin can build against a stable shape. Track A wires the
real retriever (A9) behind this contract in a follow-up.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.middleware import CurrentUser, get_current_user

router = APIRouter()


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="Natural-language query."),
    top_k: int = Query(10, ge=1, le=50),
    source: str | None = Query(None, pattern="^(github|notion)$"),
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, list[dict[str, Any]]]:
    # TODO [A9]: bridge to `backend/knowledge/retriever.py` once the retrieval
    # layer lands. Response shape is the locked contract — do not change.
    del q, top_k, source
    return {"chunks": []}
