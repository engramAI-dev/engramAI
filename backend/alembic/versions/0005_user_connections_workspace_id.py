"""Promote workspace_id to a real column on user_connections.

Notion OAuth grants per-workspace tokens, but until now the unique constraint
on (user_id, provider) forced a 2nd connection to overwrite the 1st. Promote
workspace_id from metadata_->>'workspace_id' to a real NOT NULL column and
re-key the uniqueness on (user_id, provider, workspace_id) so multiple Notion
workspaces can coexist for one user.

Backfill from existing metadata; delete rows where workspace_id can't be
derived (forces re-OAuth — acceptable in v1.5 since live row count is ~0).

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add nullable column so existing rows survive the ALTER.
    op.add_column(
        "user_connections",
        sa.Column("workspace_id", sa.String(255), nullable=True),
    )

    # 2. Backfill from the JSON metadata where the value is present.
    #    Notion's OAuth response writes workspace_id into metadata at
    #    api/routes/providers.py _upsert_connection.
    op.execute(
        """
        UPDATE user_connections
        SET workspace_id = metadata->>'workspace_id'
        WHERE provider = 'notion'
          AND metadata ? 'workspace_id'
          AND metadata->>'workspace_id' <> ''
        """
    )

    # 3. For non-Notion providers (none exist today, but future-proof) and
    #    Notion rows missing workspace_id, assign a sentinel so NOT NULL holds.
    #    Sentinel matches the legacy implicit "default" that connections/page.tsx
    #    used to hardcode for the missing-workspace case.
    op.execute(
        """
        UPDATE user_connections
        SET workspace_id = 'default'
        WHERE workspace_id IS NULL
        """
    )

    # 4. Enforce NOT NULL.
    op.alter_column("user_connections", "workspace_id", nullable=False)

    # 5. Swap unique constraints.
    op.drop_constraint(
        "uq_user_connections_user_provider",
        "user_connections",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_user_connections_user_provider_workspace",
        "user_connections",
        ["user_id", "provider", "workspace_id"],
    )


def downgrade() -> None:
    # Reverse: restore old constraint, drop new constraint + column.
    # Note: if multiple rows exist for the same (user_id, provider), the
    # restored unique constraint will fail. Caller is responsible for
    # deduplicating before downgrade.
    op.drop_constraint(
        "uq_user_connections_user_provider_workspace",
        "user_connections",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_user_connections_user_provider",
        "user_connections",
        ["user_id", "provider"],
    )
    op.drop_column("user_connections", "workspace_id")
