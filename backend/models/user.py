"""A2 — Users table model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_username: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # GitHub OAuth token. Phase 1: written encrypted-at-rest (Fernet); reads
    # fall back to plaintext for rows created before encryption landed.
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    # Phase 1: email captured via the user:email OAuth scope. Nullable — rows
    # created before the scope was added won't have it until next login.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Phase 1: account lifecycle. login/refresh reject non-active accounts.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active", default="active"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
