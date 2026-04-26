"""Create core schema tables (A2) + add FK constraints to outputs (B1 follow-up).

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25

Tables: users, documents, chunks, embeddings, conversations, messages, ingest_jobs.
Also adds the deferred FK constraints from outputs → users, messages, conversations.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("github_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("github_username", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("repo", sa.String(255), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    # --- chunks ---
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("chunk_type", sa.String(50), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    # --- embeddings (D1: separate table) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # pgvector column — added via raw SQL since Alembic doesn't natively handle vector types.
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1024) NOT NULL")
    # HNSW index for cosine similarity search.
    op.execute(
        "CREATE INDEX ix_embeddings_embedding ON embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # --- ingest_jobs ---
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("progress", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("documents_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_documents", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ingest_jobs_user_id", "ingest_jobs", ["user_id"])

    # --- Add deferred FK constraints to outputs (B1 follow-up) ---
    op.create_foreign_key(
        "fk_outputs_user_id", "outputs", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_outputs_message_id", "outputs", "messages", ["message_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_outputs_conversation_id", "outputs", "conversations", ["conversation_id"], ["id"]
    )


def downgrade() -> None:
    # Drop FK constraints on outputs first.
    op.drop_constraint("fk_outputs_conversation_id", "outputs", type_="foreignkey")
    op.drop_constraint("fk_outputs_message_id", "outputs", type_="foreignkey")
    op.drop_constraint("fk_outputs_user_id", "outputs", type_="foreignkey")

    op.drop_index("ix_ingest_jobs_user_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")

    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")

    op.execute("DROP INDEX IF EXISTS ix_embeddings_embedding")
    op.drop_table("embeddings")

    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_table("documents")

    op.drop_table("users")
