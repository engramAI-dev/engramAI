"""B6a — JWT auth middleware (FastAPI dependency).

See `docs/v1/planning/partner-b-v1-plan.md` for scope and
`docs/v1/planning/detailed/partner-b-b6a-auth-middleware.md` for design.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt  # noqa: F401

from config import settings  # noqa: F401

_ALGORITHM = "HS256"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    github_username: str


async def get_current_user(request: Request) -> CurrentUser:
    # TODO [B6a]: decode Bearer JWT, validate claims, return CurrentUser.
    raise NotImplementedError("B6a not implemented")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
