"""Phase 2 — team routes (OSS: current-team resolution).

Every user has at least one default team (backfilled in migration 0007 and
created at signup). This exposes the "current team" the rest of the app
scopes through. Team creation / invites are paid capabilities gated by
entitlements and live in the private build.
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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


async def _unique_slug(session: AsyncSession, name: str) -> str:
    base = _slugify(name)
    taken = (
        await session.execute(select(Team.id).where(Team.slug == base))
    ).scalar_one_or_none()
    return base if taken is None else f"{base}-{uuid.uuid4().hex[:6]}"


async def _count_memberships(session: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == user_id)
        )
    ).scalar_one()


@router.get("")
async def list_teams(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List the caller's workspaces (dashboard source), newest first.

    Each card carries per-membership onboarding state so the UI can badge it
    without a second call.
    """
    rows = (
        await session.execute(
            select(Team, Membership)
            .join(Membership, Membership.team_id == Team.id)
            .where(Membership.user_id == uuid.UUID(user.id))
            .order_by(Team.created_at.desc())
        )
    ).all()
    return {
        "workspaces": [
            {
                "id": str(team.id),
                "name": team.name,
                "slug": team.slug,
                "plan": team.plan,
                "role": membership.role,
                "is_default": team.is_default,
                "onboarding_state": membership.onboarding_state,
            }
            for team, membership in rows
        ]
    }


class CreateTeamRequest(BaseModel):
    name: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team(
    body: CreateTeamRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create an additional workspace.

    Multi-workspace creation is a paid/private capability: the OSS build pins
    `can_create_teams=False`, so this endpoint is disabled by entitlement and
    returns 402. When enabled, `max_workspaces` caps the count.
    """
    user_id = uuid.UUID(user.id)
    current = await resolve_current_team(session, user_id)
    plan = current[0].plan if current else "free"
    ent = get_entitlements(plan)
    if not ent.get("can_create_teams"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Creating additional workspaces isn't available on this plan",
        )
    max_workspaces = ent.get("max_workspaces")
    if max_workspaces is not None:
        count = await _count_memberships(session, user_id)
        if count >= max_workspaces:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Your plan is limited to {max_workspaces} workspaces",
            )

    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="name is required"
        )
    slug = await _unique_slug(session, name)

    team = Team(name=name, slug=slug, is_default=False, plan="free")
    session.add(team)
    await session.flush()
    session.add(Membership(team_id=team.id, user_id=user_id, role="owner"))
    await session.commit()
    return {"id": str(team.id), "name": team.name, "slug": team.slug}


class UpdateTeamRequest(BaseModel):
    name: str


@router.patch("/{team_id}")
async def update_team(
    team_id: str,
    body: UpdateTeamRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Rename a workspace. Owner only."""
    try:
        tid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )

    row = (
        await session.execute(
            select(Team, Membership.role)
            .join(Membership, Membership.team_id == Team.id)
            .where(Membership.team_id == tid, Membership.user_id == uuid.UUID(user.id))
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    team, role = row
    if role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can rename a workspace",
        )

    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="name is required"
        )
    team.name = name
    await session.commit()
    return {"id": str(team.id), "name": team.name, "slug": team.slug}
