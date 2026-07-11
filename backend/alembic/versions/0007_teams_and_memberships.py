"""Phase 2 — teams + memberships, with a default Free team backfill.

Additive: creates two tables and backfills one default team + owner
membership per existing user so the app can resolve a "current team" for
everyone immediately. No existing table is modified (resource re-homing is
the later phase B). Backward-compatible with live traffic.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-01
"""

import re
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "team"


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("plan", sa.String(16), nullable=False, server_default="free"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "memberships",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("onboarding_state", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("team_id", "user_id", name="uq_memberships_team_user"),
    )
    op.create_index("ix_memberships_team_id", "memberships", ["team_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    # --- Backfill one default Free team + owner membership per user ---
    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id, github_username FROM users")).fetchall()
    used_slugs: set[str] = set()
    for user_id, username in users:
        base = _slugify(username)
        slug = base
        n = 1
        while slug in used_slugs:
            n += 1
            slug = f"{base}-{n}"
        used_slugs.add(slug)

        team_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO teams (id, name, slug, is_default, plan, created_at) "
                "VALUES (:id, :name, :slug, true, 'free', now())"
            ),
            {"id": team_id, "name": f"{username}'s workspace", "slug": slug},
        )
        conn.execute(
            sa.text(
                "INSERT INTO memberships (id, team_id, user_id, role, created_at) "
                "VALUES (:id, :team_id, :user_id, 'owner', now())"
            ),
            {"id": uuid.uuid4(), "team_id": team_id, "user_id": user_id},
        )


def downgrade() -> None:
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_team_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("teams")
