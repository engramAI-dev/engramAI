"""A3 — GitHub OAuth flow.

Design decisions: D11 (full backend flow), D12 (query param token delivery),
D13 (24h JWT), D14 (upsert), D15 (signed JWT state), D16 (store token),
D17 (backend callback redirect).
"""

import secrets
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api import session_tokens
from api.middleware import CurrentUser, get_current_user
from config import settings
from crypto import encrypt_secret
from models.database import get_session
from models.user import User

router = APIRouter()

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_SECONDS = 60 * 60 * 24  # 24h (D13) — legacy URL token, transitional
_STATE_EXPIRY_SECONDS = 60 * 5  # 5min
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

# Phase 1 session cookies.
COOKIE_ACCESS = "engram_access"
COOKIE_REFRESH = "engram_refresh"
# Refresh cookie is scoped to the auth routes so it isn't sent on every API
# call — only /refresh and /logout need it.
_REFRESH_PATH = "/api/auth"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = settings.session_cookie_secure
    samesite = settings.session_cookie_samesite
    domain = settings.session_cookie_domain or None
    response.set_cookie(
        COOKIE_ACCESS,
        access,
        max_age=session_tokens.ACCESS_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path="/",
    )
    response.set_cookie(
        COOKIE_REFRESH,
        refresh,
        max_age=session_tokens.REFRESH_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=_REFRESH_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    domain = settings.session_cookie_domain or None
    response.delete_cookie(COOKIE_ACCESS, path="/", domain=domain)
    response.delete_cookie(COOKIE_REFRESH, path=_REFRESH_PATH, domain=domain)


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
        "scope": "read:user user:email repo",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{_GITHUB_AUTHORIZE_URL}?{query}")


async def _fetch_primary_email(github_token: str) -> str | None:
    """Fetch the user's primary verified email (needs user:email scope)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GITHUB_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json",
            },
        )
    if resp.status_code != 200:
        return None
    emails = resp.json()
    if not isinstance(emails, list):
        return None
    primary = next(
        (e for e in emails if e.get("primary") and e.get("verified")), None
    )
    chosen = primary or next((e for e in emails if e.get("verified")), None)
    return chosen.get("email") if chosen else None


@router.get("/callback")
async def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle GitHub OAuth callback: exchange code, upsert user, set session
    cookies, redirect. A legacy ?token= param is still emitted during the
    transition so an un-migrated frontend keeps working."""
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

    # 3b. Fetch primary email (G2). Falls back to the profile email.
    email = await _fetch_primary_email(github_token) or github_user.get("email")

    # 4. Upsert user (D14: ON CONFLICT). Encrypt the GH token at rest (G9).
    user_id = uuid.uuid4()
    enc_token = encrypt_secret(github_token)
    insert_values = {
        "id": user_id,
        "github_id": github_user["id"],
        "github_username": github_user["login"],
        "avatar_url": github_user.get("avatar_url"),
        "access_token": enc_token,
    }
    update_values = {
        "github_username": github_user["login"],
        "avatar_url": github_user.get("avatar_url"),
        "access_token": enc_token,
    }
    if email:
        insert_values["email"] = email
        update_values["email"] = email
    stmt = (
        pg_insert(User)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=[User.github_id],
            set_=update_values,
        )
        .returning(User.id)
    )
    result = await session.execute(stmt)
    actual_user_id = result.scalar_one()

    # 5. Create a web session (access + refresh) alongside the legacy token.
    access, refresh = await session_tokens.create_session(
        session,
        user_id=actual_user_id,
        github_username=github_user["login"],
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    await session.commit()

    # 6. Legacy 24h URL token — transitional, remove once the frontend relies
    # solely on cookies.
    legacy_token = _create_access_token(
        user_id=str(actual_user_id),
        github_username=github_user["login"],
    )
    redirect = RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={legacy_token}",
        status_code=status.HTTP_302_FOUND,
    )
    _set_auth_cookies(redirect, access, refresh)
    return redirect


@router.post("/refresh")
async def refresh(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Rotate the refresh cookie → new access + refresh cookies (fixes G7)."""
    token = request.cookies.get(COOKIE_REFRESH)
    if not token:
        resp = JSONResponse({"detail": "No refresh token"}, status_code=401)
        _clear_auth_cookies(resp)
        return resp
    try:
        access, new_refresh = await session_tokens.rotate(
            session,
            refresh_token=token,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    except session_tokens.SessionError as exc:
        # Persist any revocations written during reuse detection, then 401.
        await session.commit()
        resp = JSONResponse({"detail": str(exc)}, status_code=401)
        _clear_auth_cookies(resp)
        return resp
    await session.commit()
    resp = JSONResponse({"ok": True})
    _set_auth_cookies(resp, access, new_refresh)
    return resp


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Revoke the current session and clear cookies. Idempotent."""
    token = request.cookies.get(COOKIE_REFRESH)
    if token:
        await session_tokens.revoke_by_refresh(session, token)
        await session.commit()
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(resp)
    return resp


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Revoke all of the user's sessions (Redis denylist instant kill, G8)."""
    await session_tokens.revoke_all(session, uuid.UUID(user.id))
    await session.commit()
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(resp)
    return resp


@router.post("/mcp-tokens", status_code=status.HTTP_201_CREATED)
async def create_mcp_token(
    body: dict,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mint a 90d MCP-scoped JWT.

    The token is returned **once**; only its sha256 is persisted. Frontend
    must show it with a "copy now, you won't see it again" warning.
    """
    from api.mcp_auth import mint_mcp_token
    from models.mcp_token import McpToken

    name = (body or {}).get("name") or "Unnamed token"
    if not isinstance(name, str) or len(name) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name must be a string up to 200 chars",
        )

    token_id = uuid.uuid4()
    token, token_hash = mint_mcp_token(
        user_id=user.id,
        github_username=user.github_username,
        token_id=token_id,
    )
    record = McpToken(
        id=token_id,
        user_id=uuid.UUID(user.id),
        name=name,
        token_hash=token_hash,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": str(record.id),
        "name": record.name,
        "token": token,  # shown once
        "created_at": record.created_at.isoformat(),
    }


@router.get("/mcp-tokens")
async def list_mcp_tokens(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from models.mcp_token import McpToken

    result = await session.execute(
        select(McpToken)
        .where(McpToken.user_id == uuid.UUID(user.id))
        .order_by(McpToken.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "tokens": [
            {
                "id": str(r.id),
                "name": r.name,
                "created_at": r.created_at.isoformat(),
                "last_used_at": (
                    r.last_used_at.isoformat() if r.last_used_at else None
                ),
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
            }
            for r in rows
        ]
    }


@router.delete("/mcp-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_mcp_token(
    token_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    from datetime import datetime, timezone

    from models.mcp_token import McpToken

    try:
        tid = uuid.UUID(token_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )
    result = await session.execute(
        select(McpToken).where(
            McpToken.id == tid, McpToken.user_id == uuid.UUID(user.id)
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )
    if record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        await session.commit()


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
