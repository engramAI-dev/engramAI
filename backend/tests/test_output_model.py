"""B1 — Output model metadata tests.

Hermetic: inspects SQLAlchemy metadata only, no live DB. Integration tests
(actually INSERT/SELECT against Postgres) are DEFERRED until Track A's
`users`/`messages`/`conversations` migrations exist — until then there is
nothing to FK against and the outputs table is unreferenced by any route.
Add integration tests alongside B2 (output generator) in v1.5.
"""

import uuid

from sqlalchemy import Uuid

from models.output import Output


def test_tablename_matches_contract() -> None:
    assert Output.__tablename__ == "outputs"


def test_columns_match_api_contract() -> None:
    # Per docs/api-contract.md §Database Tables → Track B's Tables.
    expected = {
        "id",
        "user_id",
        "message_id",
        "conversation_id",
        "type",
        "title",
        "content",
        "metadata",
        "created_at",
    }
    actual = {col.name for col in Output.__table__.columns}
    assert actual == expected


def test_python_metadata_attr_maps_to_db_metadata_column() -> None:
    # `.metadata` is reserved on DeclarativeBase; Python attr is `output_metadata`.
    col = Output.__table__.c["metadata"]
    assert col is not None
    assert Output.output_metadata.key == "output_metadata"


def test_id_is_uuid_type() -> None:
    assert isinstance(Output.__table__.c.id.type, Uuid)


def test_id_default_produces_uuid() -> None:
    default = Output.__table__.c.id.default
    assert default is not None
    value = default.arg(None) if callable(default.arg) else default.arg
    assert isinstance(value, uuid.UUID)


def test_nullability_matches_contract() -> None:
    # user_id + title + content + type + created_at + metadata are NOT NULL;
    # message_id + conversation_id are nullable.
    t = Output.__table__
    assert t.c.user_id.nullable is False
    assert t.c.type.nullable is False
    assert t.c.title.nullable is False
    assert t.c.content.nullable is False
    assert t.c.metadata.nullable is False
    assert t.c.created_at.nullable is False
    assert t.c.message_id.nullable is True
    assert t.c.conversation_id.nullable is True


def test_fk_hints_present_on_orm_even_though_migration_omits_constraints() -> None:
    # FK hints stay in the model for ORM join semantics; the migration
    # intentionally does NOT emit DB-level FK constraints until Track A's
    # users/messages/conversations tables exist.
    t = Output.__table__
    assert any(fk.target_fullname == "users.id" for fk in t.c.user_id.foreign_keys)
    assert any(fk.target_fullname == "messages.id" for fk in t.c.message_id.foreign_keys)
    assert any(
        fk.target_fullname == "conversations.id" for fk in t.c.conversation_id.foreign_keys
    )
