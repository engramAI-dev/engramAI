"""Phase 1 — sessions table + user email/status/deleted_at.

Additive and backward-compatible: new columns are nullable or carry a
server_default, so existing rows and the current auth path are unaffected.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: email + account lifecycle (additive) ---
    op.add_column("users", sa.Column("email", sa.String(320), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- sessions: refresh-token store ---
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "rotated_from",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "status")
    op.drop_column("users", "email")
