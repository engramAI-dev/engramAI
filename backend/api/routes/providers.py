"""Provider integration routes — list, connect, disconnect data sources."""

import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from config import settings
from crypto import decrypt_secret
from models.database import get_session
from models.ingest_job import IngestJob
from models.user import User
from models.user_connection import UserConnection

router = APIRouter()

# ---------------------------------------------------------------------------
# Known provider definitions
# ---------------------------------------------------------------------------
_PROVIDERS = [
    {"id": "github", "name": "GitHub", "auth_type": "oauth"},
    {"id": "notion", "name": "Notion", "auth_type": "oauth"},
]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class NotionWorkspaceInfo(BaseModel):
    workspace_id: str
    workspace_name: str
    metadata: dict[str, Any] = {}


class ProviderInfo(BaseModel):
    id: str
    name: str
    auth_type: str
    connected: bool
    metadata: dict[str, Any] = {}
    # Only populated for providers that support multiple per-user
    # connections (currently just Notion). Each entry corresponds to one
    # row in user_connections. None means "this provider has at most one
    # connection per user" (e.g. github via users.access_token).
    workspaces: list[NotionWorkspaceInfo] | None = None


class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    description: str | None = None
    private: bool
    language: str | None = None
    updated_at: str


class NotionPage(BaseModel):
    id: str
    title: str
    url: str
    last_edited: str


class ConnectResponse(BaseModel):
    redirect_url: str | None = None
    connected: bool = False


class TokenBody(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# GET /providers — list providers with connection status
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[ProviderInfo])
async def list_providers(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderInfo]:
    """Return all known providers with per-user connection status.

    For Notion, populates `workspaces` with one entry per connected
    workspace so the frontend can render multi-workspace UIs without
    a second round-trip.
    """
    result = await session.execute(
        select(UserConnection).where(
            UserConnection.user_id == uuid.UUID(user.id)
        )
    )
    # Group by provider so Notion can hold multiple workspaces.
    by_provider: dict[str, list[UserConnection]] = {}
    for c in result.scalars().all():
        by_provider.setdefault(c.provider, []).append(c)

    out: list[ProviderInfo] = []
    for p in _PROVIDERS:
        if p["id"] == "github":
            # GitHub is always connected via the users table token; the
            # connection isn't stored in user_connections at all.
            out.append(
                ProviderInfo(
                    id=p["id"],
                    name=p["name"],
                    auth_type=p["auth_type"],
                    connected=True,
                    metadata={"username": user.github_username},
                )
            )
        elif p["id"] == "notion":
            conns = by_provider.get("notion", [])
            workspaces = [
                NotionWorkspaceInfo(
                    workspace_id=c.workspace_id,
                    workspace_name=str(c.metadata_.get("workspace_name", "")),
                    metadata=c.metadata_,
                )
                for c in conns
            ]
            out.append(
                ProviderInfo(
                    id=p["id"],
                    name=p["name"],
                    auth_type=p["auth_type"],
                    connected=len(workspaces) > 0,
                    metadata={},
                    workspaces=workspaces,
                )
            )
        else:
            conns = by_provider.get(p["id"], [])
            out.append(
                ProviderInfo(
                    id=p["id"],
                    name=p["name"],
                    auth_type=p["auth_type"],
                    connected=len(conns) > 0,
                    metadata=conns[0].metadata_ if conns else {},
                )
            )
    return out


# ---------------------------------------------------------------------------
# GET /providers/github/resources — list repos
# ---------------------------------------------------------------------------
@router.get("/github/resources", response_model=list[GitHubRepo])
async def list_github_repos(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[GitHubRepo]:
    """List the authenticated user's GitHub repositories."""
    result = await session.execute(
        select(User.access_token).where(User.id == uuid.UUID(user.id))
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not found",
        )
    token = decrypt_secret(token)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user/repos",
            params={"per_page": 100, "sort": "updated"},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {resp.status_code}",
        )

    repos = resp.json()
    return [
        GitHubRepo(
            id=r["id"],
            name=r["name"],
            full_name=r["full_name"],
            description=r.get("description"),
            private=r["private"],
            language=r.get("language"),
            updated_at=r["updated_at"],
        )
        for r in repos
    ]


# ---------------------------------------------------------------------------
# GET /providers/notion/resources — list pages
# ---------------------------------------------------------------------------
@router.get("/notion/resources", response_model=list[NotionPage])
async def list_notion_pages(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NotionPage]:
    """List accessible Notion pages for a specific connected workspace."""
    token = await _get_notion_token(user, session, workspace_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Notion workspace '{workspace_id}' not connected",
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/search",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={"filter": {"value": "page", "property": "object"}},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Notion API error: {resp.status_code}",
        )

    pages = resp.json().get("results", [])
    return [
        NotionPage(
            id=p["id"],
            title=_extract_notion_title(p),
            url=p.get("url", ""),
            last_edited=p.get("last_edited_time", ""),
        )
        for p in pages
    ]


# ---------------------------------------------------------------------------
# POST /providers/notion/connect — initiate Notion OAuth or API key
# ---------------------------------------------------------------------------
@router.post("/notion/connect", response_model=ConnectResponse)
async def connect_notion(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectResponse:
    """Start Notion OAuth flow or connect with a global API key."""
    if not settings.notion_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion OAuth not configured on server (set NOTION_CLIENT_ID)",
        )

    redirect_url = (
        "https://api.notion.com/v1/oauth/authorize"
        f"?client_id={settings.notion_client_id}"
        f"&redirect_uri={settings.notion_redirect_uri}"
        "&response_type=code"
        "&owner=user"
        f"&state={user.id}"
    )
    return ConnectResponse(redirect_url=redirect_url)


# ---------------------------------------------------------------------------
# GET /providers/notion/callback — OAuth callback
# ---------------------------------------------------------------------------
@router.get("/notion/callback")
async def notion_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Exchange Notion OAuth code for an access token and store it."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/oauth/token",
            auth=(settings.notion_client_id, settings.notion_client_secret),
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.notion_redirect_uri,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Notion token exchange failed: {resp.text}",
        )

    data = resp.json()
    access_token = data["access_token"]
    # Notion always returns workspace_id for OAuth tokens; fall back to
    # "default" only if it's missing (defensive, shouldn't happen).
    workspace_id = data.get("workspace_id") or "default"
    workspace_name = data.get("workspace_name", "")

    user_id = uuid.UUID(state)
    await _upsert_connection(
        session,
        user_id=user_id,
        provider="notion",
        workspace_id=workspace_id,
        access_token=access_token,
        metadata_={
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
        },
    )

    # Kick off this workspace's ingest immediately. The worker scopes
    # delete-old-docs by workspace_id so other connected workspaces are
    # untouched. "Connection done" and "ingest queued" are effectively
    # the same event from the user's POV.
    job_id = uuid.uuid4()
    session.add(
        IngestJob(
            id=job_id,
            user_id=user_id,
            source="notion",
            source_url=workspace_id,
            status="queued",
        )
    )
    await session.commit()

    from ingestion.notion import ingest_notion_workspace

    ingest_notion_workspace.delay(
        job_id=str(job_id),
        notion_api_key=access_token,
        user_id=str(user_id),
        workspace_id=workspace_id,
    )

    return RedirectResponse(
        url=f"{settings.frontend_url}/connections?notion_indexing={job_id}"
    )


# ---------------------------------------------------------------------------
# POST /providers/notion/disconnect
# ---------------------------------------------------------------------------
@router.post("/notion/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_notion(
    workspace_id: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove a Notion workspace connection.

    If `workspace_id` is provided, removes only that workspace's row.
    If omitted, removes ALL of the user's Notion connections — kept for
    convenience in dev/admin flows. Note: this only deletes the OAuth
    token; indexed Notion documents stay in the library until the next
    re-ingest cycle (the worker scopes its delete-old-docs by
    workspace_id).
    """
    stmt = delete(UserConnection).where(
        UserConnection.user_id == uuid.UUID(user.id),
        UserConnection.provider == "notion",
    )
    if workspace_id is not None:
        stmt = stmt.where(UserConnection.workspace_id == workspace_id)
    await session.execute(stmt)
    await session.commit()


# ---------------------------------------------------------------------------
# POST /providers/{provider_id}/token — save an API token directly
# ---------------------------------------------------------------------------
@router.post("/{provider_id}/token", status_code=status.HTTP_200_OK)
async def save_token(
    provider_id: str,
    body: TokenBody,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    """Upsert an API token for self-hosted setups that use keys over OAuth."""
    known_ids = {p["id"] for p in _PROVIDERS}
    if provider_id not in known_ids or provider_id == "github":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot set token for provider '{provider_id}'",
        )

    # Generic token-auth providers don't have a workspace concept; use
    # the "default" sentinel to satisfy the NOT NULL workspace_id column.
    await _upsert_connection(
        session,
        user_id=uuid.UUID(user.id),
        provider=provider_id,
        workspace_id="default",
        access_token=body.token,
        metadata_={},
    )
    return {"connected": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_notion_token(
    user: CurrentUser,
    session: AsyncSession,
    workspace_id: str,
) -> str | None:
    """Return the user's Notion token for a specific workspace."""
    result = await session.execute(
        select(UserConnection.access_token).where(
            UserConnection.user_id == uuid.UUID(user.id),
            UserConnection.provider == "notion",
            UserConnection.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def _upsert_connection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    workspace_id: str,
    access_token: str,
    metadata_: dict[str, Any],
) -> None:
    """Insert or update a user_connection row keyed by (user, provider, workspace).

    For providers that don't have a workspace concept, callers pass
    workspace_id="default" — matches the convention enforced by the
    NOT NULL workspace_id column in migration 0005.
    """
    stmt = pg_insert(UserConnection).values(
        id=uuid.uuid4(),
        user_id=user_id,
        provider=provider,
        workspace_id=workspace_id,
        access_token=access_token,
        metadata_=metadata_,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            UserConnection.user_id,
            UserConnection.provider,
            UserConnection.workspace_id,
        ],
        set_={
            "access_token": stmt.excluded.access_token,
            "metadata": stmt.excluded.metadata,
        },
    )
    await session.execute(stmt)
    await session.commit()


def _extract_notion_title(page: dict[str, Any]) -> str:
    """Best-effort title extraction from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return "".join(t.get("plain_text", "") for t in title_parts)
    return "Untitled"
