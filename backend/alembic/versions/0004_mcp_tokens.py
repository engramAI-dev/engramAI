"""Add mcp_tokens table for long-lived MCP-scoped JWTs.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mcp_tokens_user_id", "mcp_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_tokens_user_id", table_name="mcp_tokens")
    op.drop_table("mcp_tokens")
