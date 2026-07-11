"""B6a — JWT auth middleware (FastAPI dependency).

See `docs/v1/planning/partner-b-v1-plan.md` for scope and
`docs/v1/planning/detailed/partner-b-b6a-auth-middleware.md` for design.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt

from config import settings

_ALGORITHM = "HS256"
# Keep in sync with api.routes.auth.COOKIE_ACCESS. Hardcoded here to avoid a
# circular import (auth imports this module).
_ACCESS_COOKIE = "engram_access"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    github_username: str


def _extract_token(request: Request) -> str | None:
    """Access token from the Authorization header (legacy/MCP clients) or the
    httpOnly access cookie (web sessions). Header wins when both are present."""
    header = request.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return request.cookies.get(_ACCESS_COOKIE)


async def get_current_user(request: Request) -> CurrentUser:
    token = _extract_token(request)
    if not token:
        raise _unauthorized("Not authenticated")

    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except ExpiredSignatureError:
        raise _unauthorized("Token expired")
    except JWTError:
        raise _unauthorized("Invalid token")

    user_id = claims.get("sub")
    username = claims.get("github_username")
    if not user_id or not username:
        raise _unauthorized("Invalid token")

    # MCP-scoped tokens (90d) require a DB lookup to honor revocation.
    if claims.get("scope") == "mcp":
        # Local import to avoid circulars: middleware loads early.
        from api.mcp_auth import verify_mcp_token
        from models.database import async_session

        async with async_session() as session:
            ok = await verify_mcp_token(token, claims, session)
        if not ok:
            raise _unauthorized("Token revoked")
    elif claims.get("type") == "access":
        # Web session token: stateless (15-min TTL is the ordinary kill
        # window). Only the Redis instant-kill denylist is consulted, for
        # "log out all devices" / suspend. Fails open on Redis outage.
        sid = claims.get("sid")
        if sid:
            from api.session_tokens import is_denied

            if await is_denied(sid):
                raise _unauthorized("Session revoked")

    user = CurrentUser(id=user_id, github_username=username)
    request.state.user = user
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
