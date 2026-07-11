"""Phase 2 — membership model (user ↔ team).

Access control scopes through memberships, never a direct user→resource link.
Onboarding is per-user-per-team, so `onboarding_state` lives here (decision
2026-07-01, structure spec §5.1). One owner membership is auto-created with
each user's default team.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_memberships_team_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="member", default="member"
    )  # owner | admin | member
    # Per-user-per-team onboarding progress (null until onboarding starts).
    onboarding_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
