"""Phase 2 — team routes (OSS: current-team resolution).

Every user has at least one default team (backfilled in migration 0007 and
created at signup). This exposes the "current team" the rest of the app
scopes through. Team creation / invites are paid capabilities gated by
entitlements and live in the private build.
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.entitlements import get_entitlements
from api.middleware import CurrentUser, get_current_user
from models.database import get_session
from models.membership import Membership
from models.team import Team

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "team"


async def ensure_default_team(
    session: AsyncSession, user_id: uuid.UUID, username: str
) -> None:
    """Idempotently ensure the user has a default team + owner membership.

    Called at signup so new users get a workspace (the migration only
    backfilled users that existed when it ran). No-op if they already have
    any membership. Caller owns the commit.
    """
    existing = (
        await session.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == user_id)
        )
    ).scalar_one()
    if existing:
        return

    base = _slugify(username)
    taken = (
        await session.execute(select(Team.id).where(Team.slug == base))
    ).scalar_one_or_none()
    slug = base if taken is None else f"{base}-{user_id.hex[:6]}"

    team = Team(name=f"{username}'s workspace", slug=slug, is_default=True, plan="free")
    session.add(team)
    await session.flush()
    session.add(Membership(team_id=team.id, user_id=user_id, role="owner"))


async def resolve_current_team(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[Team, str] | None:
    """The user's current team (default first), with their role."""
    stmt = (
        select(Team, Membership.role)
        .join(Membership, Membership.team_id == Team.id)
        .where(Membership.user_id == user_id)
        .order_by(Team.is_default.desc(), Team.created_at.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).first()


@router.get("/current")
async def current_team(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Current team + plan + entitlements snapshot for the authed user."""
    row = await resolve_current_team(session, uuid.UUID(user.id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No team for user"
        )
    team, role = row
    return {
        "id": str(team.id),
        "name": team.name,
        "slug": team.slug,
        "is_default": team.is_default,
        "plan": team.plan,
        "role": role,
        "entitlements": get_entitlements(team.plan),
    }
