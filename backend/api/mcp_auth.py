"""B14-remote — MCP-scoped token mint + verify helpers.

Two-tier auth:

  - **Session JWT** (24h, `scope` absent or != "mcp"): from
    `/api/auth/callback`, used by the web frontend.
  - **MCP token** (90d, `scope == "mcp"`, `token_id` claim): minted by
    `/api/auth/mcp-tokens`, hashed and stored in `mcp_tokens`. Pasted
    by the user into Claude Desktop / Cursor / claude.ai.

The middleware (`api.middleware.get_current_user`) decodes the JWT;
when it sees `scope == "mcp"` it calls `verify_mcp_token` here, which
checks the hash exists in the table, isn't revoked, and bumps
`last_used_at`. Adds ~1ms per request — acceptable at v1.5 traffic.
"""

import hashlib
import time
import uuid
from datetime import datetime, timezone

from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.mcp_token import McpToken

_ALGORITHM = "HS256"
_MCP_TOKEN_EXPIRY_SECONDS = 60 * 60 * 24 * 90  # 90 days


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mint_mcp_token(
    user_id: str, github_username: str, token_id: uuid.UUID, team_id: str
) -> tuple[str, str]:
    """Return `(jwt, sha256_hash)`. The JWT is shown to the user once;
    the hash is what we persist."""
    payload = {
        "sub": user_id,
        "github_username": github_username,
        "scope": "mcp",
        "token_id": str(token_id),
        "team_id": team_id,
        "exp": int(time.time()) + _MCP_TOKEN_EXPIRY_SECONDS,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)
    return token, _hash(token)


async def verify_mcp_token(
    raw_token: str, claims: dict, session: AsyncSession
) -> bool:
    """Confirm the token's hash is in `mcp_tokens` and not revoked.

    Bumps `last_used_at` opportunistically — failures don't block the
    request (the auth decision is already made by the JWT signature
    + `revoked_at IS NULL` check).
    """
    token_id = claims.get("token_id")
    if not token_id:
        return False

    try:
        token_uuid = uuid.UUID(token_id)
    except (TypeError, ValueError):
        return False

    result = await session.execute(
        select(McpToken).where(McpToken.id == token_uuid)
    )
    record = result.scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        return False
    if record.token_hash != _hash(raw_token):
        return False

    record.last_used_at = datetime.now(timezone.utc)
    await session.commit()
    return True
