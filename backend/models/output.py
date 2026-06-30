"""B1 — `outputs` table model.

Layer 2 (built in v1, not user-visible) per
`docs/v1/planning/partner-b-v1-plan.md`. Schema mirrors
`docs/api-contract.md` §Database Tables → Partner B's Tables.

FK constraints are NOT emitted at the DB level yet — see the companion
migration `alembic/versions/0001_outputs.py`. The `ForeignKey(...)` hints
below stay for ORM join semantics once A's tables exist.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class Output(Base):
    __tablename__ = "outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    # TODO [B1]: FK constraints land once Partner A's migration creates
    # `users`, `messages`, `conversations`. Hints kept for ORM joins.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("messages.id"), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("conversations.id"), nullable=True
    )

    type: Mapped[str] = mapped_column(String(50))  # 'code_snippet' | 'summary' | 'report'
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    # `.metadata` is reserved on DeclarativeBase — use `output_metadata` in Python,
    # map to DB column `"metadata"` per the contract.
    output_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
