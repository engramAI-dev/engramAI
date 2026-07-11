"""Re-home per-user resources to per-workspace (team_id) — phase A.

Knowledge, connections, jobs, conversations, outputs and MCP tokens become
workspace-scoped. This is the backward-compatible first phase for live traffic:
`team_id` is added NULLABLE and backfilled from each row's owner's default team.
A follow-up migration tightens it to NOT NULL once the app reliably sets it on
every write.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_TABLES = [
    ("user_connections", "ix_user_connections_team_id"),
    ("documents", "ix_documents_team_id"),
    ("ingest_jobs", "ix_ingest_jobs_team_id"),
    ("conversations", "ix_conversations_team_id"),
    ("outputs", "ix_outputs_team_id"),
    ("mcp_tokens", "ix_mcp_tokens_team_id"),
]

_UC_NAME = "uq_user_connections_user_provider_workspace"

# Backfill team_id from the owner's default team (falls back to their oldest).
_BACKFILL = """
UPDATE {table} AS t
SET team_id = (
    SELECT tm.id FROM teams tm
    JOIN memberships m ON m.team_id = tm.id
    WHERE m.user_id = t.user_id
    ORDER BY tm.is_default DESC, tm.created_at ASC
    LIMIT 1
)
WHERE t.team_id IS NULL
"""


def upgrade() -> None:
    for table, index_name in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "team_id",
                sa.Uuid(),
                sa.ForeignKey("teams.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
        op.create_index(index_name, table, ["team_id"])
        op.execute(_BACKFILL.format(table=table))

    # Same provider workspace may now be connected in two Engram workspaces, so
    # team_id joins the uniqueness key.
    op.drop_constraint(_UC_NAME, "user_connections", type_="unique")
    op.create_unique_constraint(
        _UC_NAME, "user_connections", ["user_id", "team_id", "provider", "workspace_id"]
    )


def downgrade() -> None:
    op.drop_constraint(_UC_NAME, "user_connections", type_="unique")
    op.create_unique_constraint(
        _UC_NAME, "user_connections", ["user_id", "provider", "workspace_id"]
    )
    for table, index_name in _TABLES:
        op.drop_index(index_name, table_name=table)
        op.drop_column(table, "team_id")
