"""Active-workspace resolution for request scoping (2026-07-11 re-home).

Every workspace-scoped write/read resolves the caller's *active* workspace:
the `X-Workspace-Id` header the frontend sends when the user has entered a
workspace, validated against membership. Absent/blank header falls back to the
user's most-recent workspace. A user with zero workspaces gets 409 — the
frontend routes them to the dashboard.
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from models.database import get_session
from models.membership import Membership
from models.team import Team


async def get_active_team_id(
    x_workspace_id: str | None = Header(default=None),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """Resolve the workspace (team) this request operates on."""
    user_id = uuid.UUID(user.id)

    # 1. Explicit active workspace — must be one the user belongs to.
    if x_workspace_id:
        try:
            tid = uuid.UUID(x_workspace_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Workspace-Id",
            )
        member = (
            await session.execute(
                select(Membership.id).where(
                    Membership.user_id == user_id, Membership.team_id == tid
                )
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this workspace",
            )
        return tid

    # 2. Fallback: most-recent workspace (default first for single-tier).
    tid = (
        await session.execute(
            select(Team.id)
            .join(Membership, Membership.team_id == Team.id)
            .where(Membership.user_id == user_id)
            .order_by(Team.is_default.desc(), Team.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No workspace; create one first",
        )
    return tid
