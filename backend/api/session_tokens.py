"""Phase 1 — web session tokens: mint, rotate, revoke.

Access token: short-lived (15 min) HS256 JWT carrying `sid` (session id) and
`type="access"`. Stateless — its TTL is the ordinary kill window.

Refresh token: opaque random string, 30-day sliding, stored only as a
SHA-256 hash in the `sessions` table, one row per device/login. Rotated on
every use; presenting an already-rotated (revoked) refresh token is treated
as reuse and revokes the user's whole session set.

Instant kill: `revoke_all` also pushes each session id onto a Redis denylist
(TTL = access TTL) that the middleware checks per request, so "log out all
devices" takes effect before the 15-min access TTL elapses. Redis errors
fail open (availability over the belt) — refresh revocation is the primary
control. See `docs/v1/planning/onboarding-and-accounts-design.md` §4.
"""

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.session import Session
from models.user import User

_ALGORITHM = "HS256"
ACCESS_TTL_SECONDS = 15 * 60  # 15 min
REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days, sliding

_DENYLIST_PREFIX = "session:denied:"


class SessionError(Exception):
    """Base for recoverable auth-session failures (mapped to 401)."""


class InvalidRefresh(SessionError):
    pass


class ReuseDetected(SessionError):
    pass


class ExpiredRefresh(SessionError):
    pass


class InactiveUser(SessionError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def mint_access_token(user_id: str, github_username: str, session_id: uuid.UUID) -> str:
    payload = {
        "sub": user_id,
        "github_username": github_username,
        "sid": str(session_id),
        "type": "access",
        "exp": int(time.time()) + ACCESS_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


# --------------------------------------------------------------------------
# Redis denylist (instant kill). Lazy client; fail-open on any error.
# --------------------------------------------------------------------------

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def deny_session(session_id: uuid.UUID) -> None:
    try:
        await _get_redis().set(
            f"{_DENYLIST_PREFIX}{session_id}", "1", ex=ACCESS_TTL_SECONDS
        )
    except Exception:  # noqa: BLE001 — belt, not primary control
        pass


async def is_denied(session_id: str) -> bool:
    try:
        return bool(await _get_redis().get(f"{_DENYLIST_PREFIX}{session_id}"))
    except Exception:  # noqa: BLE001 — fail open on Redis outage
        return False


# --------------------------------------------------------------------------
# Session lifecycle
# --------------------------------------------------------------------------


async def create_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    github_username: str,
    user_agent: str | None,
    ip: str | None,
) -> tuple[str, str]:
    """Create a session row and return (access_token, refresh_token).

    The caller owns the commit.
    """
    refresh = generate_refresh_token()
    row = Session(
        user_id=user_id,
        refresh_hash=_hash_refresh(refresh),
        user_agent=user_agent,
        ip=ip,
    )
    db.add(row)
    await db.flush()  # populate row.id
    access = mint_access_token(str(user_id), github_username, row.id)
    return access, refresh


async def rotate(
    db: AsyncSession,
    *,
    refresh_token: str,
    user_agent: str | None,
    ip: str | None,
) -> tuple[str, str]:
    """Rotate a refresh token → (new_access, new_refresh). Caller commits.

    Raises a SessionError subclass on any failure.
    """
    h = _hash_refresh(refresh_token)
    row = (
        await db.execute(select(Session).where(Session.refresh_hash == h))
    ).scalar_one_or_none()
    if row is None:
        raise InvalidRefresh("Unknown refresh token")

    if row.revoked_at is not None:
        # A revoked (already-rotated or logged-out) token was replayed →
        # reuse. Revoke the user's whole session set defensively.
        await _revoke_all_rows(db, row.user_id)
        raise ReuseDetected("Refresh token reuse detected")

    if _now() - row.last_used_at > timedelta(seconds=REFRESH_TTL_SECONDS):
        row.revoked_at = _now()
        raise ExpiredRefresh("Refresh token expired")

    user = (
        await db.execute(select(User).where(User.id == row.user_id))
    ).scalar_one_or_none()
    if user is None or user.status != "active":
        raise InactiveUser("Account is not active")

    # Rotate: consume the old row, chain a new one.
    new_refresh = generate_refresh_token()
    new_row = Session(
        user_id=row.user_id,
        refresh_hash=_hash_refresh(new_refresh),
        rotated_from=row.id,
        user_agent=user_agent,
        ip=ip,
    )
    db.add(new_row)
    await db.flush()
    row.revoked_at = _now()
    access = mint_access_token(str(user.id), user.github_username, new_row.id)
    return access, new_refresh


async def revoke_by_refresh(db: AsyncSession, refresh_token: str) -> None:
    """Revoke the session for a given refresh token (logout). Idempotent."""
    h = _hash_refresh(refresh_token)
    row = (
        await db.execute(select(Session).where(Session.refresh_hash == h))
    ).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = _now()
        await deny_session(row.id)


async def _revoke_all_rows(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    ids = list(
        (
            await db.execute(
                select(Session.id).where(
                    Session.user_id == user_id, Session.revoked_at.is_(None)
                )
            )
        ).scalars()
    )
    if ids:
        await db.execute(
            update(Session)
            .where(Session.id.in_(ids))
            .values(revoked_at=_now())
        )
    return ids


async def revoke_all(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every active session for a user and push them to the denylist."""
    ids = await _revoke_all_rows(db, user_id)
    for sid in ids:
        await deny_session(sid)
