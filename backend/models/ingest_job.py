"""A2/A8 — Ingest jobs table model (D7/D8: own table, no Celery result backend)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Workspace (team) the job runs for; the worker reads it to scope the
    # Documents it creates (2026-07-11 re-home, phase A — nullable + backfilled).
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # 'github' | 'notion'
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="queued"
    )  # queued | processing | embedding | complete | failed
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    documents_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_documents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
