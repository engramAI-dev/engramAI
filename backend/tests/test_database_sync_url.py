"""Regression test for `_to_sync_url`.

asyncpg accepts `ssl=require`; psycopg2 only accepts `sslmode=require`.
The sync engine driving Celery's sync sessions must transform both the
driver prefix and the SSL query param.
"""

from models.database import _to_sync_url


def test_swaps_driver_and_ssl_param():
    src = "postgresql+asyncpg://u:p@h/db?ssl=require"
    assert _to_sync_url(src) == "postgresql+psycopg2://u:p@h/db?sslmode=require"


def test_swaps_ssl_when_not_first_param():
    src = "postgresql+asyncpg://u:p@h/db?foo=1&ssl=require"
    assert _to_sync_url(src) == "postgresql+psycopg2://u:p@h/db?foo=1&sslmode=require"


def test_passthrough_when_no_ssl_param():
    src = "postgresql+asyncpg://u:p@h/db"
    assert _to_sync_url(src) == "postgresql+psycopg2://u:p@h/db"


def test_passthrough_when_already_sslmode():
    src = "postgresql+asyncpg://u:p@h/db?sslmode=require"
    assert _to_sync_url(src) == "postgresql+psycopg2://u:p@h/db?sslmode=require"
