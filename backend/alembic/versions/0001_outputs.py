"""Create outputs table (B1).

Revision ID: 0001
Revises:
Create Date: 2026-04-20

v1 scope note: FK constraints to Track A's `users`, `messages`, and
`conversations` tables are intentionally NOT emitted yet — those tables
do not exist in any migration. Columns are present as plain UUIDs.
When A's migration lands, add the FKs in a follow-up revision.
See `docs/v1/planning/partner-b-v1-plan.md` §Layer 2 (resolved decision).
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outputs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # TODO [B1]: add FK constraints once Track A's migration creates
        # `users`, `messages`, `conversations`. Columns stay as plain UUIDs
        # until then so `alembic upgrade head` is self-applicable.
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_outputs_user_id", "outputs", ["user_id"])
    op.create_index("ix_outputs_message_id", "outputs", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_outputs_message_id", table_name="outputs")
    op.drop_index("ix_outputs_user_id", table_name="outputs")
    op.drop_table("outputs")
