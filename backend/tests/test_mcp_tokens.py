"""B14-remote — MCP-scoped token tests.

Covers the mint helper, the verify helper, and the middleware integration
(scope=mcp triggers a DB lookup; revoked tokens are rejected).

Hermetic where possible: the mint+verify pair is pure and exercised
without a DB; the middleware integration uses a stubbed session that
mimics the SQLAlchemy interface we touch.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException, Request
from jose import jwt

from api import middleware as middleware_mod
from api.mcp_auth import _hash, mint_mcp_token, verify_mcp_token
from api.middleware import get_current_user
from config import settings

TEAM_ID = "00000000-0000-0000-0000-0000000000bb"


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {"type": "http", "headers": raw}
    return Request(scope)


class _FakeRecord:
    def __init__(self, token_hash: str, revoked: bool = False) -> None:
        self.token_hash = token_hash
        self.revoked_at: datetime | None = (
            datetime.now(timezone.utc) if revoked else None
        )
        self.last_used_at: datetime | None = None


class _FakeResult:
    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record

    def scalar_one_or_none(self) -> _FakeRecord | None:
        return self._record


class _FakeSession:
    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record
        self.commits = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._record)

    async def commit(self) -> None:
        self.commits += 1

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


def test_mint_emits_scope_and_token_id() -> None:
    tid = uuid.uuid4()
    token, token_hash = mint_mcp_token("u1", "alice", tid, TEAM_ID)
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert claims["scope"] == "mcp"
    assert claims["token_id"] == str(tid)
    assert claims["sub"] == "u1"
    assert token_hash == _hash(token)
    # 90d expiry — within a generous window
    assert claims["exp"] > int(time.time()) + 60 * 60 * 24 * 89


@pytest.mark.asyncio
async def test_verify_accepts_valid_token() -> None:
    tid = uuid.uuid4()
    token, token_hash = mint_mcp_token("u1", "alice", tid, TEAM_ID)
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    session = _FakeSession(_FakeRecord(token_hash))
    assert await verify_mcp_token(token, claims, session) is True
    assert session.commits == 1  # last_used_at bumped


@pytest.mark.asyncio
async def test_verify_rejects_revoked_token() -> None:
    tid = uuid.uuid4()
    token, token_hash = mint_mcp_token("u1", "alice", tid, TEAM_ID)
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    session = _FakeSession(_FakeRecord(token_hash, revoked=True))
    assert await verify_mcp_token(token, claims, session) is False


@pytest.mark.asyncio
async def test_verify_rejects_unknown_token() -> None:
    tid = uuid.uuid4()
    token, _ = mint_mcp_token("u1", "alice", tid, TEAM_ID)
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    session = _FakeSession(None)
    assert await verify_mcp_token(token, claims, session) is False


@pytest.mark.asyncio
async def test_verify_rejects_hash_mismatch() -> None:
    tid = uuid.uuid4()
    token, _ = mint_mcp_token("u1", "alice", tid, TEAM_ID)
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    session = _FakeSession(_FakeRecord("deadbeef" * 8))
    assert await verify_mcp_token(token, claims, session) is False


@pytest.mark.asyncio
async def test_middleware_rejects_revoked_mcp_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tid = uuid.uuid4()
    token, token_hash = mint_mcp_token("u1", "alice", tid, TEAM_ID)
    revoked_session = _FakeSession(_FakeRecord(token_hash, revoked=True))

    def _factory() -> _FakeSession:
        return revoked_session

    # The middleware imports `async_session` lazily inside the function,
    # so patch the module the middleware imports from.
    import models.database as db_mod

    monkeypatch.setattr(db_mod, "async_session", _factory)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            _request({"Authorization": f"Bearer {token}"})
        )
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token revoked"


@pytest.mark.asyncio
async def test_middleware_passes_session_jwt_unchanged(mint_jwt: Any) -> None:
    """Plain session JWTs (no scope claim) skip the DB lookup entirely."""
    token = mint_jwt(
        {"sub": "u1", "github_username": "alice", "exp": int(time.time()) + 60}
    )
    user = await get_current_user(_request({"Authorization": f"Bearer {token}"}))
    assert user.id == "u1"
    # Sanity: middleware module didn't crash even though no DB is configured.
    assert middleware_mod  # type: ignore[truthy-bool]
