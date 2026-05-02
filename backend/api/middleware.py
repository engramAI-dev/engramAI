"""B6a — JWT auth middleware (FastAPI dependency).

See `docs/v1/planning/partner-b-v1-plan.md` for scope and
`docs/v1/planning/detailed/partner-b-b6a-auth-middleware.md` for design.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt

from config import settings

_ALGORITHM = "HS256"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    github_username: str


async def get_current_user(request: Request) -> CurrentUser:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise _unauthorized("Not authenticated")

    token = header.split(" ", 1)[1].strip()
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
    # Session JWTs (24h) skip this — their short lifetime is the
    # revocation surface.
    if claims.get("scope") == "mcp":
        # Local import to avoid circulars: middleware loads early.
        from api.mcp_auth import verify_mcp_token
        from models.database import async_session

        async with async_session() as session:
            ok = await verify_mcp_token(token, claims, session)
        if not ok:
            raise _unauthorized("Token revoked")

    user = CurrentUser(id=user_id, github_username=username)
    request.state.user = user
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
