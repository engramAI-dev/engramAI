"""A3 — GitHub OAuth flow.

Design decisions: D11 (full backend flow), D12 (query param token delivery),
D13 (24h JWT), D14 (upsert), D15 (signed JWT state), D16 (store token),
D17 (backend callback redirect).
"""

import secrets
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from config import settings
from models.database import get_session
from models.user import User

router = APIRouter()

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_SECONDS = 60 * 60 * 24  # 24h (D13)
_STATE_EXPIRY_SECONDS = 60 * 5  # 5min
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


def _create_access_token(user_id: str, github_username: str) -> str:
    """Mint a JWT that B's middleware can validate."""
    payload = {
        "sub": user_id,
        "github_username": github_username,
        "exp": int(time.time()) + _TOKEN_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def _create_state_token() -> str:
    """Mint a short-lived signed JWT for OAuth CSRF protection (D15)."""
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "exp": int(time.time()) + _STATE_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def _verify_state_token(state: str) -> None:
    """Verify the OAuth state JWT. Raises HTTPException on failure."""
    try:
        jwt.decode(state, settings.secret_key, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect user to GitHub OAuth authorization page."""
    state = _create_state_token()
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "read:user repo",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{_GITHUB_AUTHORIZE_URL}?{query}")


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle GitHub OAuth callback: exchange code, upsert user, redirect with JWT."""
    # 1. Verify CSRF state (D15)
    _verify_state_token(state)

    # 2. Exchange code for GitHub access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            _GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()

    github_token = token_data.get("access_token")
    if not github_token:
        error = token_data.get("error_description", "Failed to get access token")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # 3. Fetch GitHub user profile
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub user profile",
            )
        github_user = user_resp.json()

    # 4. Upsert user (D14: ON CONFLICT)
    user_id = uuid.uuid4()
    stmt = (
        pg_insert(User)
        .values(
            id=user_id,
            github_id=github_user["id"],
            github_username=github_user["login"],
            avatar_url=github_user.get("avatar_url"),
            access_token=github_token,
        )
        .on_conflict_do_update(
            index_elements=[User.github_id],
            set_={
                "github_username": github_user["login"],
                "avatar_url": github_user.get("avatar_url"),
                "access_token": github_token,
            },
        )
        .returning(User.id)
    )
    result = await session.execute(stmt)
    actual_user_id = result.scalar_one()
    await session.commit()

    # 5. Mint session JWT
    token = _create_access_token(
        user_id=str(actual_user_id),
        github_username=github_user["login"],
    )

    # 6. Redirect to frontend with token (D12: query param)
    return RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={token}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/me")
async def me(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return the currently authenticated user's profile."""
    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user.id))
    )
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {
        "id": str(db_user.id),
        "github_username": db_user.github_username,
        "avatar_url": db_user.avatar_url,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }
