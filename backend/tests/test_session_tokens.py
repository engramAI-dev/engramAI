"""Phase 1 — web session token service (hermetic; DB rotation covered in E2E)."""

import time
import uuid
from typing import Any

import pytest
from jose import jwt

from api import session_tokens
from config import settings


def test_access_token_claims() -> None:
    sid = uuid.uuid4()
    token = session_tokens.mint_access_token("user-1", "octocat", sid)
    claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert claims["sub"] == "user-1"
    assert claims["github_username"] == "octocat"
    assert claims["sid"] == str(sid)
    assert claims["type"] == "access"
    ttl = claims["exp"] - int(time.time())
    assert 0 < ttl <= session_tokens.ACCESS_TTL_SECONDS


def test_refresh_tokens_unique_and_hashed() -> None:
    a, b = session_tokens.generate_refresh_token(), session_tokens.generate_refresh_token()
    assert a != b
    assert len(session_tokens._hash_refresh(a)) == 64
    # Hash is deterministic for a given token.
    assert session_tokens._hash_refresh(a) == session_tokens._hash_refresh(a)


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


@pytest.mark.asyncio
async def test_deny_and_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(session_tokens, "_get_redis", lambda: fake)
    sid = uuid.uuid4()
    assert await session_tokens.is_denied(str(sid)) is False
    await session_tokens.deny_session(sid)
    assert await session_tokens.is_denied(str(sid)) is True


@pytest.mark.asyncio
async def test_is_denied_fails_open_on_redis_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom() -> Any:
        raise RuntimeError("redis down")

    monkeypatch.setattr(session_tokens, "_get_redis", _boom)
    # An outage must not lock everyone out.
    assert await session_tokens.is_denied(str(uuid.uuid4())) is False
