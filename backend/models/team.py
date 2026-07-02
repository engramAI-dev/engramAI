"""Phase 2 — team model.

The team is the unit of scoping (decision 2026-07-01). A "personal
workspace" is just a team with a single owner membership (`is_default=true`).
Plan/entitlements/usage attach to the team, never the user. See
`docs/v1/planning/onboarding-and-accounts-design.md` §5.1.

Schema is identical in the OSS and paid builds; only entitlements differ. In
the OSS build every user has exactly one default Free team.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # true = the auto-created personal workspace (cannot be deleted).
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    # Denormalized current tier. free | pro. OSS build is always "free".
    plan: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="free", default="free"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
