"""B14-remote — MCP token model.

Long-lived tokens for the remote `/mcp` transport. Session JWTs minted
by `/api/auth/callback` last 24h; that's wrong for an MCP connector
the user pastes once into Claude Desktop / Cursor and forgets about.

We store only a SHA-256 hash of the JWT — the token itself is shown to
the user exactly once at creation. Revocation flips `revoked_at`; the
middleware checks the table on each request when a JWT carries
`scope == "mcp"`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class McpToken(Base):
    __tablename__ = "mcp_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
