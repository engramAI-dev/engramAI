"""B1 — `outputs` table model.

Layer 2 (built in v1, not user-visible) per
`docs/v1/planning/partner-b-v1-plan.md`. Schema mirrors
`docs/api-contract.md` §Database Tables → Track B's Tables.

FKs reference Track A's tables by string name — A's models do not
exist yet but SQLAlchemy resolves string refs lazily at metadata bind.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class Output(Base):
    __tablename__ = "outputs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # TODO [B1]: confirm with Track A's migration — table names assumed from api-contract.md.
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("messages.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=True
    )

    type: Mapped[str] = mapped_column(String(50))  # 'code_snippet' | 'summary' | 'report'
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    output_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
