"""B6a — auth middleware tests.

Cases mirror `docs/v1/planning/detailed/partner-b-b6a-auth-middleware.md`.
Hermetic: no HTTP, just the dependency called with a fake `Request`.
"""

import time
from typing import Any

import pytest
from fastapi import HTTPException, Request

from api.middleware import CurrentUser, get_current_user


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {"type": "http", "headers": raw}
    return Request(scope)


@pytest.mark.asyncio
async def test_valid_token_returns_current_user(mint_jwt: Any) -> None:
    token = mint_jwt({"sub": "u1", "github_username": "alice", "exp": int(time.time()) + 60})
    user = await get_current_user(_request({"Authorization": f"Bearer {token}"}))
    assert user == CurrentUser(id="u1", github_username="alice")


@pytest.mark.asyncio
async def test_missing_header_returns_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request())
    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_wrong_scheme_returns_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request({"Authorization": "Basic abc"}))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_bad_signature_returns_401() -> None:
    from jose import jwt
    bad = jwt.encode(
        {"sub": "u1", "github_username": "alice", "exp": int(time.time()) + 60},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request({"Authorization": f"Bearer {bad}"}))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


@pytest.mark.asyncio
async def test_expired_token_returns_401(mint_jwt: Any) -> None:
    token = mint_jwt({"sub": "u1", "github_username": "alice", "exp": int(time.time()) - 60})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request({"Authorization": f"Bearer {token}"}))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expired"


@pytest.mark.asyncio
async def test_missing_sub_claim_returns_401(mint_jwt: Any) -> None:
    token = mint_jwt({"github_username": "alice", "exp": int(time.time()) + 60})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_request({"Authorization": f"Bearer {token}"}))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"
