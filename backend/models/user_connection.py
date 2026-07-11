"""UserConnection model — stores per-user provider tokens (Notion, etc.)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class UserConnection(Base):
    __tablename__ = "user_connections"
    __table_args__ = (
        # workspace_id is part of the key so a user can hold multiple Notion
        # workspace OAuth tokens at once. For providers where the concept
        # doesn't apply, the convention is workspace_id = "default".
        UniqueConstraint(
            "user_id",
            "team_id",
            "provider",
            "workspace_id",
            name="uq_user_connections_user_provider_workspace",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Engram workspace (team) this connection belongs to (2026-07-11 re-home,
    # phase A). Distinct from `workspace_id` below, which is the *provider's*
    # workspace (e.g. the Notion workspace).
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB(), nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
